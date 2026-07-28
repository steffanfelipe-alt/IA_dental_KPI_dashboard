"""
evals/casos_dorados.py

Valores correctos para los fixtures de evals/fixtures/, calculados a mano
UNA vez a partir de los mismos arrays que generar_fixtures.py usa para
escribir los archivos — así nunca hay dos números "verdaderos" que puedan
desincronizarse entre sí.

`PERIODO_VIGENTE` es el último mes (Abril 2026): es lo que
`evaluar_cobertura` debe reportar como valor "actual" de cada variable una
vez que exista la dimensión de período (Fase 2). `PROMEDIO_4_MESES` es la
cuenta correcta sin la fila TOTAL/Prom. — sirve para verificar que esa fila
no se está mezclando en ningún promedio (el bug real de la Fase 1.1).
"""

from generar_fixtures import (
    ASISTEN,
    CONSULTAS_NUEVAS,
    COBRADO,
    FACTURADO,
    HORAS_TAREA_MANUAL_SEMANA,
    MESES,
    PRESUP_ACEPTADOS,
    PRESUP_ENTREGADOS,
    TIEMPO_RESPUESTA_HORAS,
    TRANSACCIONES,
    TRATAM_COMPLETADOS,
    TURNOS_AGENDADOS,
    _no_shows,
)

IDX_VIGENTE = -1  # Abril 2026, el último mes del fixture
NO_SHOWS = _no_shows(ASISTEN, TURNOS_AGENDADOS)

# ---------------------------------------------------------------------------
# Variables — valor del período vigente (Abril 2026)
# ---------------------------------------------------------------------------

VARIABLES_ESPERADAS_VIGENTE = {
    "consultas_nuevas_mes": CONSULTAS_NUEVAS[IDX_VIGENTE],
    "turnos_agendados": TURNOS_AGENDADOS[IDX_VIGENTE],
    "no_shows": NO_SHOWS[IDX_VIGENTE],
    "presupuestos_emitidos": PRESUP_ENTREGADOS[IDX_VIGENTE],
    "presupuestos_aceptados": PRESUP_ACEPTADOS[IDX_VIGENTE],
    "tratamientos_completados": TRATAM_COMPLETADOS[IDX_VIGENTE],
    "monto_cobrado": COBRADO[IDX_VIGENTE],
    "monto_facturado": FACTURADO[IDX_VIGENTE],
    # 6.5 horas -> minutos: el punto del hallazgo C (conversión de unidades)
    "tiempo_respuesta_promedio_min": TIEMPO_RESPUESTA_HORAS * 60,
    "horas_tarea_manual_semana": {"total": float(HORAS_TAREA_MANUAL_SEMANA)},
}

# Promedio correcto de los 4 meses reales, EXCLUYENDO la fila TOTAL/Prom.
# — es lo que un cálculo de "promedio del período" tiene que dar si la fila
# total no se coló como un quinto mes.
PROMEDIO_4_MESES = {
    "consultas_nuevas_mes": sum(CONSULTAS_NUEVAS) / len(CONSULTAS_NUEVAS),
    "turnos_agendados": sum(TURNOS_AGENDADOS) / len(TURNOS_AGENDADOS),
    "presupuestos_emitidos": sum(PRESUP_ENTREGADOS) / len(PRESUP_ENTREGADOS),
    "presupuestos_aceptados": sum(PRESUP_ACEPTADOS) / len(PRESUP_ACEPTADOS),
    "tratamientos_completados": sum(TRATAM_COMPLETADOS) / len(TRATAM_COMPLETADOS),
}

# Lo que da si (bug real observado y verificado contra el archivo real de
# la clínica) se promedia incluyendo la fila TOTAL/Prom. como si fuera un
# período más: esa fila YA contiene la suma de los meses, así que
# promediar_incluyéndola equivale a sumar el total dos veces y dividir por
# n+1 — sirve para afirmar que el sistema NO cae en este valor.
PROMEDIO_CON_BUG_TOTAL = {
    var: 2 * suma / (len(CONSULTAS_NUEVAS) + 1)
    for var, suma in {
        "consultas_nuevas_mes": sum(CONSULTAS_NUEVAS),
        "turnos_agendados": sum(TURNOS_AGENDADOS),
    }.items()
}

# ---------------------------------------------------------------------------
# KPIs — calculados sobre el período vigente
# ---------------------------------------------------------------------------

KPIS_ESPERADOS_VIGENTE = {
    1: CONSULTAS_NUEVAS[IDX_VIGENTE],
    2: TIEMPO_RESPUESTA_HORAS * 60,
    3: round(100 * TURNOS_AGENDADOS[IDX_VIGENTE] / CONSULTAS_NUEVAS[IDX_VIGENTE], 1),
    4: round(100 * NO_SHOWS[IDX_VIGENTE] / TURNOS_AGENDADOS[IDX_VIGENTE], 1),
    5: round(100 * PRESUP_ACEPTADOS[IDX_VIGENTE] / PRESUP_ENTREGADOS[IDX_VIGENTE], 1),
    7: round(100 * TRATAM_COMPLETADOS[IDX_VIGENTE] / PRESUP_ACEPTADOS[IDX_VIGENTE], 1),
    13: round(100 * COBRADO[IDX_VIGENTE] / FACTURADO[IDX_VIGENTE], 1),
    15: float(HORAS_TAREA_MANUAL_SEMANA),
}

# ---------------------------------------------------------------------------
# CSV transaccional: variables tipo dict agrupadas por categoría
# ---------------------------------------------------------------------------

_ACEPTADOS = [t for t in TRANSACCIONES if t[2] == "aceptado"]

INGRESO_POR_TRATAMIENTO_ESPERADO: dict[str, float] = {}
for tratamiento, monto, _ in _ACEPTADOS:
    INGRESO_POR_TRATAMIENTO_ESPERADO[tratamiento] = (
        INGRESO_POR_TRATAMIENTO_ESPERADO.get(tratamiento, 0) + monto
    )

PRESUPUESTOS_EMITIDOS_CSV = len(TRANSACCIONES)
PRESUPUESTOS_ACEPTADOS_CSV = len(_ACEPTADOS)
MONTO_PRESUPUESTOS_ACEPTADOS_CSV = sum(m for _, m, _ in _ACEPTADOS)
TICKET_PROMEDIO_CSV = round(MONTO_PRESUPUESTOS_ACEPTADOS_CSV / PRESUPUESTOS_ACEPTADOS_CSV, 2)

# ---------------------------------------------------------------------------
# Trampas a propósito — variables que NO deben colarse tal cual
# ---------------------------------------------------------------------------

# La columna "Tasa no-show" (0.219...) NUNCA debe terminar como el valor de
# no_shows (que es un CONTEO, no una tasa) — es exactamente el hallazgo 1.3
# reproducido: confundir la tasa con el conteo.
TASA_NO_SHOW_VIGENTE = NO_SHOWS[IDX_VIGENTE] / TURNOS_AGENDADOS[IDX_VIGENTE]

# La hoja "Operativo" mezcla horas, %, y conteos en la misma columna
# "Valor" — ninguna de las otras 3 métricas de esa hoja debe terminar
# pisando a horas_tarea_manual_semana ni viceversa.
