"""
metricas_paciente.py

Fase 2 del plan de evolución: las métricas que la identidad de paciente
(matching.py + ledger.py) desbloquea y que las 20 fórmulas de schema.py no
pueden expresar por diseño — KPI 4 (no-show), por ejemplo, es un agregado:
"22% de no-show" no distingue 40 pacientes fallando una vez de 6 fallando
siempre, y son dos problemas con dos intervenciones distintas.

Deliberadamente NO viven en `schema.KPI_FORMULAS`: ese registro corresponde
1:1 a la tabla de 20 KPIs del Miro (ver docstring de schema.py) y agregar
17 fórmulas ahí rompería ese contrato con todo lo que asume "son 20 KPIs"
(coverage.py, priorizacion.py, interpretacion.py). Esta es una capa aparte
que opera sobre `ledger_pacientes` — ver ledger.py para el contrato de
eventos y la nota de scope sobre extracción en vivo.

Principio general: una métrica que necesita un tipo de evento puntual y no
lo encuentra simplemente no cuenta ese registro — nunca asume qué era un
evento de tipo desconocido o ausente.
"""

from typing import Optional

from periodos import orden_cronologico


def _eventos_de_tipo(eventos: list[dict], tipo: str) -> list[dict]:
    return [e for e in eventos if e.get("tipo_evento") == tipo]


def _periodo_mas_reciente(ledger: dict[str, list[dict]]) -> Optional[str]:
    periodos = {e["periodo"] for eventos in ledger.values() for e in eventos}
    return orden_cronologico(periodos)[-1] if periodos else None


def _diferencia_meses(desde: str, hasta: str) -> Optional[int]:
    """"2026-01" -> "2026-04" da 3. Aproximación mensual, no de días
    exactos — consistente con el resto del sistema (benchmarks.py ya
    expresa el umbral de "paciente inactivo" en meses, no en días)."""
    try:
        a_y, a_m = (int(x) for x in desde.split("-"))
        b_y, b_m = (int(x) for x in hasta.split("-"))
    except (ValueError, AttributeError):
        return None
    return (b_y - a_y) * 12 + (b_m - a_m)


# ---------------------------------------------------------------------------
# Riesgo y fuga
# ---------------------------------------------------------------------------

def no_show_recurrente(ledger: dict, umbral_tasa: float = 0.3, minimo_turnos: int = 3) -> dict[str, float]:
    """{paciente_id: tasa_no_show} solo para quienes tienen al menos
    `minimo_turnos` turnos registrados y una tasa >= `umbral_tasa` — con
    una sola cita no hay tasa que tenga sentido marcar como "recurrente"."""
    resultado = {}
    for pid, eventos in ledger.items():
        asistidos = len(_eventos_de_tipo(eventos, "turno_asistido"))
        no_shows = len(_eventos_de_tipo(eventos, "turno_no_show"))
        total = asistidos + no_shows
        if total < minimo_turnos:
            continue
        tasa = no_shows / total
        if tasa >= umbral_tasa:
            resultado[pid] = round(tasa, 3)
    return resultado


def pacientes_en_riesgo_de_fuga(
    ledger: dict, periodo_actual: Optional[str] = None,
    meses_riesgo_desde: int = 6, meses_inactivo_desde: int = 14,
) -> list[str]:
    """Pacientes cuyo último evento fue hace >= `meses_riesgo_desde` meses
    pero < `meses_inactivo_desde` (el umbral de "ya inactivo" que
    benchmarks.py documenta para el KPI 9) — la zona intermedia donde
    todavía se los puede recuperar antes de que se pierdan del todo."""
    periodo_actual = periodo_actual or _periodo_mas_reciente(ledger)
    if periodo_actual is None:
        return []
    resultado = []
    for pid, eventos in ledger.items():
        ultimo = orden_cronologico({e["periodo"] for e in eventos})[-1]
        meses = _diferencia_meses(ultimo, periodo_actual)
        if meses is not None and meses_riesgo_desde <= meses < meses_inactivo_desde:
            resultado.append(pid)
    return resultado


def porcentaje_base_inactiva(ledger: dict, periodo_actual: Optional[str] = None, umbral_meses: int = 14) -> Optional[float]:
    periodo_actual = periodo_actual or _periodo_mas_reciente(ledger)
    if periodo_actual is None or not ledger:
        return None
    inactivos = 0
    for eventos in ledger.values():
        ultimo = orden_cronologico({e["periodo"] for e in eventos})[-1]
        meses = _diferencia_meses(ultimo, periodo_actual)
        if meses is not None and meses >= umbral_meses:
            inactivos += 1
    return round(100 * inactivos / len(ledger), 1)


def dias_desde_ultimo_contacto(ledger: dict, periodo_actual: Optional[str] = None) -> dict[str, int]:
    """Aproximado a partir de la diferencia en meses (30.4 días/mes) — el
    ledger guarda período, no fecha exacta garantizada para cada evento."""
    periodo_actual = periodo_actual or _periodo_mas_reciente(ledger)
    if periodo_actual is None:
        return {}
    resultado = {}
    for pid, eventos in ledger.items():
        ultimo = orden_cronologico({e["periodo"] for e in eventos})[-1]
        meses = _diferencia_meses(ultimo, periodo_actual)
        if meses is not None:
            resultado[pid] = round(meses * 30.4)
    return resultado


# ---------------------------------------------------------------------------
# Valor y concentración
# ---------------------------------------------------------------------------

def ltv_real(ledger: dict) -> dict[str, float]:
    """Suma de eventos "pago" por paciente — dinero efectivamente cobrado,
    no presupuestado (misma distinción que monto_cobrado vs
    monto_facturado en schema.py)."""
    resultado = {}
    for pid, eventos in ledger.items():
        pagos = [e["monto"] for e in _eventos_de_tipo(eventos, "pago") if isinstance(e.get("monto"), (int, float))]
        if pagos:
            resultado[pid] = round(sum(pagos), 2)
    return resultado


def ticket_promedio_por_cliente(ledger: dict) -> dict[str, float]:
    resultado = {}
    for pid, eventos in ledger.items():
        pagos = [e["monto"] for e in _eventos_de_tipo(eventos, "pago") if isinstance(e.get("monto"), (int, float))]
        if pagos:
            resultado[pid] = round(sum(pagos) / len(pagos), 2)
    return resultado


def concentracion_ingresos(ledger: dict, top_pct: float = 0.10) -> Optional[dict]:
    """Qué % de la facturación total genera el top `top_pct` de pacientes
    por LTV. Un LTV promedio sano puede convivir con una concentración
    peligrosa (3 pacientes = 80% de los ingresos) — son datos distintos,
    y esto es lo que la Fase 4 (diagnóstico) necesita para no confundir
    "buen promedio" con "negocio frágil"."""
    ltv = ltv_real(ledger)
    if not ltv:
        return None
    ordenados = sorted(ltv.items(), key=lambda kv: kv[1], reverse=True)
    n_top = max(1, round(len(ordenados) * top_pct))
    total = sum(v for _, v in ordenados)
    if total <= 0:
        return None
    top = ordenados[:n_top]
    return {
        "top_pct": top_pct,
        "n_pacientes_top": n_top,
        "share_ingresos": round(sum(v for _, v in top) / total, 3),
        "pacientes_top": [pid for pid, _ in top],
    }


def mix_tratamientos_por_paciente(ledger: dict) -> dict[str, dict[str, int]]:
    resultado = {}
    for pid, eventos in ledger.items():
        conteo: dict[str, int] = {}
        for e in eventos:
            tratamiento = e.get("tratamiento")
            if tratamiento:
                conteo[tratamiento] = conteo.get(tratamiento, 0) + 1
        if conteo:
            resultado[pid] = conteo
    return resultado


# ---------------------------------------------------------------------------
# Ciclo de vida
# ---------------------------------------------------------------------------

def retencion_por_cohorte_alta(ledger: dict) -> dict[str, float]:
    """{período_de_alta: % de esa cohorte con algún evento posterior}.
    La cohorte es el período del PRIMER evento "alta" de cada paciente."""
    cohortes: dict[str, list[str]] = {}  # periodo_cohorte -> [pid, ...]
    ultimo_evento: dict[str, str] = {}
    for pid, eventos in ledger.items():
        altas = _eventos_de_tipo(eventos, "alta")
        if not altas:
            continue
        periodo_alta = orden_cronologico({e["periodo"] for e in altas})[0]
        cohortes.setdefault(periodo_alta, []).append(pid)
        ultimo_evento[pid] = orden_cronologico({e["periodo"] for e in eventos})[-1]

    resultado = {}
    for periodo_cohorte, pacientes in cohortes.items():
        retenidos = sum(1 for pid in pacientes if ultimo_evento[pid] > periodo_cohorte)
        resultado[periodo_cohorte] = round(100 * retenidos / len(pacientes), 1)
    return resultado


def intervalo_medio_entre_visitas(ledger: dict) -> dict[str, float]:
    """Meses promedio entre turnos asistidos consecutivos, por paciente.
    Requiere al menos 2 turnos asistidos — con uno solo no hay intervalo."""
    resultado = {}
    for pid, eventos in ledger.items():
        periodos = orden_cronologico({e["periodo"] for e in _eventos_de_tipo(eventos, "turno_asistido")})
        if len(periodos) < 2:
            continue
        brechas = [_diferencia_meses(periodos[i], periodos[i + 1]) for i in range(len(periodos) - 1)]
        brechas = [b for b in brechas if b is not None]
        if brechas:
            resultado[pid] = round(sum(brechas) / len(brechas), 2)
    return resultado


def abandono_a_mitad_tratamiento(ledger: dict) -> list[str]:
    """Pacientes con un tratamiento iniciado pero sin el completado
    correspondiente — la P22 de la guía de diagnóstico, medida en vez de
    solo preguntada."""
    resultado = []
    for pid, eventos in ledger.items():
        iniciados = len(_eventos_de_tipo(eventos, "tratamiento_iniciado"))
        completados = len(_eventos_de_tipo(eventos, "tratamiento_completado"))
        if iniciados > completados:
            resultado.append(pid)
    return resultado


# ---------------------------------------------------------------------------
# Atribución
# ---------------------------------------------------------------------------

def nuevos_vs_recurrentes(ledger: dict, periodo: str) -> dict[str, int]:
    """Para un período dado: cuántos pacientes con actividad en ese
    período son "nuevos" (su primer evento de todos fue ese período) vs.
    "recurrentes" (ya tenían historia previa) — a diferencia de
    consultas_nuevas_mes (autorreportado, probablemente mezcla ambos)."""
    nuevos, recurrentes = 0, 0
    for eventos in ledger.values():
        periodos_paciente = orden_cronologico({e["periodo"] for e in eventos})
        if periodo not in periodos_paciente:
            continue
        if periodos_paciente[0] == periodo:
            nuevos += 1
        else:
            recurrentes += 1
    return {"nuevos": nuevos, "recurrentes": recurrentes}


def atribucion_referidos(ledger: dict) -> dict[str, int]:
    """{paciente_id: cuántos pacientes nuevos trajo}, contando eventos
    "referido_recibido" registrados en el ledger del paciente que refirió."""
    resultado = {}
    for pid, eventos in ledger.items():
        n = len(_eventos_de_tipo(eventos, "referido_recibido"))
        if n:
            resultado[pid] = n
    return resultado


# ---------------------------------------------------------------------------
# Agregadas
# ---------------------------------------------------------------------------

def tasa_segunda_visita(ledger: dict) -> Optional[float]:
    """% de pacientes con >= 2 turnos asistidos entre los que tienen >= 1.
    El leading indicator más temprano de retención: se ve meses antes que
    KPI 8 (recall), que depende de que ya haya pasado el ciclo de alta."""
    con_una_o_mas = [pid for pid, eventos in ledger.items() if _eventos_de_tipo(eventos, "turno_asistido")]
    if not con_una_o_mas:
        return None
    con_dos_o_mas = sum(1 for pid in con_una_o_mas if len(_eventos_de_tipo(ledger[pid], "turno_asistido")) >= 2)
    return round(100 * con_dos_o_mas / len(con_una_o_mas), 1)


def velocidad_presupuesto_a_aceptacion(ledger: dict) -> dict[str, float]:
    """Meses entre un presupuesto emitido y su aceptación, por paciente
    (emparejados en orden — el primer emitido con el primer aceptado
    posterior). Le dice al seguimiento automático CUÁNDO insistir, algo
    que KPI 5 (tasa de aceptación agregada) no puede decir."""
    resultado = {}
    for pid, eventos in ledger.items():
        emitidos = orden_cronologico({e["periodo"] for e in _eventos_de_tipo(eventos, "presupuesto_emitido")})
        aceptados = orden_cronologico({e["periodo"] for e in _eventos_de_tipo(eventos, "presupuesto_aceptado")})
        pares = []
        for emitido in emitidos:
            posteriores = [a for a in aceptados if a >= emitido]
            if posteriores:
                pares.append(_diferencia_meses(emitido, posteriores[0]))
        pares = [p for p in pares if p is not None]
        if pares:
            resultado[pid] = round(sum(pares) / len(pares), 2)
    return resultado


def multi_tratamiento_vs_mono(ledger: dict) -> Optional[dict]:
    mix = mix_tratamientos_por_paciente(ledger)
    if not mix:
        return None
    multi = sum(1 for tratamientos in mix.values() if len(tratamientos) > 1)
    return {
        "multi_tratamiento_pct": round(100 * multi / len(mix), 1),
        "mono_tratamiento_pct": round(100 * (len(mix) - multi) / len(mix), 1),
    }


def estacionalidad_observada_por_paciente(ledger: dict) -> dict[str, int]:
    """No-shows agrupados por MES CALENDARIO (01-12, sin importar el año)
    — el insumo empírico para contrastar contra lo que el dueño declaró en
    P51 (¿coincide la estacionalidad real con la percibida? — ver
    estacionalidad.py, Fase 4)."""
    conteo: dict[str, int] = {}
    for eventos in ledger.values():
        for e in _eventos_de_tipo(eventos, "turno_no_show"):
            mes = e["periodo"].split("-")[1] if "-" in e.get("periodo", "") else None
            if mes:
                conteo[mes] = conteo.get(mes, 0) + 1
    return dict(sorted(conteo.items()))


def calcular_todas(ledger: dict, periodo_actual: Optional[str] = None) -> dict:
    """Bundle de las 17 métricas — conveniencia para el runner manual y
    para lo que eventualmente alimente diagnostico.py (Fase 4)."""
    periodo_actual = periodo_actual or _periodo_mas_reciente(ledger)
    return {
        "no_show_recurrente": no_show_recurrente(ledger),
        "pacientes_en_riesgo_de_fuga": pacientes_en_riesgo_de_fuga(ledger, periodo_actual),
        "porcentaje_base_inactiva": porcentaje_base_inactiva(ledger, periodo_actual),
        "dias_desde_ultimo_contacto": dias_desde_ultimo_contacto(ledger, periodo_actual),
        "ltv_real": ltv_real(ledger),
        "ticket_promedio_por_cliente": ticket_promedio_por_cliente(ledger),
        "concentracion_ingresos": concentracion_ingresos(ledger),
        "mix_tratamientos_por_paciente": mix_tratamientos_por_paciente(ledger),
        "retencion_por_cohorte_alta": retencion_por_cohorte_alta(ledger),
        "intervalo_medio_entre_visitas": intervalo_medio_entre_visitas(ledger),
        "abandono_a_mitad_tratamiento": abandono_a_mitad_tratamiento(ledger),
        "nuevos_vs_recurrentes": nuevos_vs_recurrentes(ledger, periodo_actual) if periodo_actual else None,
        "atribucion_referidos": atribucion_referidos(ledger),
        "tasa_segunda_visita": tasa_segunda_visita(ledger),
        "velocidad_presupuesto_a_aceptacion": velocidad_presupuesto_a_aceptacion(ledger),
        "multi_tratamiento_vs_mono": multi_tratamiento_vs_mono(ledger),
        "estacionalidad_observada_por_paciente": estacionalidad_observada_por_paciente(ledger),
    }
