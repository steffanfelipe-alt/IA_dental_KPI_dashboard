"""
interpretacion.py

Acá vive la idea central de este módulo: un gap contra un benchmark
("tu tasa de aceptación es 45%, el benchmark es 60-70%") es un dato, no un
diagnóstico. El diagnóstico aparece cuando ese número se cruza con el
contexto cualitativo de la clínica — las respuestas de la Guía de
Diagnóstico que NO alimentan ninguna fórmula (P1, P2, P5-P7, P10-P12,
P19-P20, P24-P38, P44-P53) pero explican el porqué.

Ejemplo real de por qué esto importa: si la tasa de aceptación está baja
Y el dueño contestó que no hacen ningún seguimiento de presupuestos
(P20), el gap confirma un problema de proceso — automatizar el
seguimiento debería mover la aguja. Pero si la tasa está baja Y el dueño
ya hace seguimiento tres veces (P20) y de todas formas no aceptan, el
problema probablemente no es de proceso sino de precio/poder adquisitivo
de la zona — automatizar el seguimiento ahí no sirve de mucho, y el
asistente tiene que poder decir eso en vez de recomendar a ciegas
"automatizá el seguimiento" solo porque el número está bajo.

Este módulo no reemplaza el motor de priorización (gap × impacto,
priorizacion.py) del diseño original — lo alimenta con el contexto que le
falta para razonar, en vez de rankear puramente por magnitud del gap.

Además del cruce gap + contexto cualitativo, dos ideas del research de
benchmarks (`referencias/benchmarks_research_AR.md`) están incorporadas acá:
- La firmeza de la comparación depende de qué tan confiable es el
  benchmark usado (§4.1) y de que las fuentes de KPIs digitales tienen
  sesgo comercial (§4.2) — ver SYSTEM_PROMPT_BASE.
- El peso del benchmark externo baja a medida que la clínica junta su
  propio historial (§4.4) — ver `peso_benchmark_vs_historial`.
"""

import dataclasses
import json
from typing import Optional

from schema import KPI_BY_ID
from benchmarks import calcular_gap, Gap
from claude_utils import extraer_texto, respuesta_truncada
from formato import fmt_por_unidad
# Re-exportados desde contexto_cualitativo.py (Fase 4): se movieron ahí
# para romper un import circular con diagnostico.py, que también los
# necesita. Quien ya los importaba desde acá (ver test_benchmarks.py)
# sigue funcionando igual.
from contexto_cualitativo import (  # noqa: F401
    CONTEXTO_CUALITATIVO_POR_KPI,
    CONTEXTO_GENERAL,
    construir_contexto_cualitativo,
)

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


MODEL = "claude-sonnet-5"


def _serializar_diagnostico(diagnostico):
    """Acepta un `diagnostico.Diagnostico`, una lista de ellos, o None —
    sin importar el módulo diagnostico.py (evita el import circular: ese
    módulo ya importa de acá contexto_cualitativo indirectamente).
    dataclasses.asdict funciona sobre cualquier dataclass sin conocer su
    tipo concreto."""
    if diagnostico is None:
        return None
    if isinstance(diagnostico, list):
        return [dataclasses.asdict(d) if dataclasses.is_dataclass(d) else d for d in diagnostico]
    if dataclasses.is_dataclass(diagnostico):
        return dataclasses.asdict(diagnostico)
    return diagnostico


def peso_benchmark_vs_historial(semanas_de_datos_propios: int) -> dict:
    """
    El peso del benchmark externo baja a medida que la clínica acumula su
    propio historial en kpi_snapshots — al principio no hay con qué
    comparar más que la referencia externa (débil); con el tiempo, la
    tendencia propia de la clínica es más confiable que cualquier proxy.
    """
    if semanas_de_datos_propios < 4:
        return {"benchmark": 0.8, "historial": 0.2}   # recién arranca: se apoya en referencia externa (débil)
    elif semanas_de_datos_propios < 12:
        return {"benchmark": 0.5, "historial": 0.5}   # transición
    else:
        return {"benchmark": 0.2, "historial": 0.8}   # ya tiene su propia línea base: manda lo propio


SEMANAS_POR_PERIODO_MENSUAL = 4.33  # mismo factor que schema._horas_liberadas


def semanas_desde_serie(serie: Optional[dict]) -> int:
    """
    Aproxima cuántas semanas de datos propios representa una serie de
    períodos mensuales (mismo supuesto de 4.33 semanas/mes que ya usa
    `schema._horas_liberadas`). Antes de esto, todo llamador dejaba
    `semanas_de_datos_propios` en 0 por defecto — la ponderación siempre
    terminaba apoyándose al máximo en el benchmark externo (débil en 11
    de 13 KPIs) aunque la clínica ya tuviera meses de historial propio
    (hallazgo 4 del informe de deficiencias).
    """
    if not serie:
        return 0
    return round(len(serie) * SEMANAS_POR_PERIODO_MENSUAL)


SYSTEM_PROMPT_BASE = """Sos el asistente de diagnóstico de Agencia IA para
clínicas dentales en Argentina. Tu trabajo NO es leer un número de gap en
voz alta — es explicar qué significa ese número dado el contexto real de
ESTA clínica, y decir qué hacer al respecto.

Reglas de razonamiento:

1. Un KPI fuera del benchmark no es automáticamente el problema a
   resolver — puede ser el SÍNTOMA de algo que las respuestas cualitativas
   ya explican. Si el contexto cualitativo ya da la causa (ej: "no hacen
   ningún seguimiento de presupuestos"), decilo explícitamente en vez de
   solo repetir el número.

2. Si el contexto cualitativo CONTRADICE lo que el número sugeriría (ej:
   la clínica ya automatiza la confirmación de turnos y aun así el
   no-show está alto), señalá esa contradicción — probablemente el
   problema real es otro (tipo de paciente, zona, precio) y hay que
   decirlo en vez de recomendar una automatización que no va a ayudar.

3. La firmeza con la que comparás depende de `confiabilidad_benchmark`:
   - "oficial" (ej. arancel del Círculo Odontológico): afirmá con
     seguridad, es un dato argentino real.
   - "consultora_ar": afirmá, pero aclarando que es una estimación de
     consultora/prensa argentina, no una estadística oficial.
   - "proxy_internacional": presentalo como orientación ("como
     referencia internacional, no como dato argentino") — nunca con la
     misma firmeza que un benchmark oficial.
   - "sin_benchmark": no compares contra nada externo — analizá la
     tendencia propia de la clínica en el tiempo (¿mejoró o empeoró
     respecto al período anterior?).

4. Sesgo comercial de las fuentes: la mayoría de los proxies de KPIs
   digitales (tiempo de respuesta, agendamiento, reactivación, CAC,
   producción por hora) vienen de software o agencias que venden la
   solución al problema que miden. Sus cifras de "mejora" (ej. "reduce
   no-show 40%") son DIRECCIÓN, no magnitud garantizada. Nunca las uses
   como promesa en una oferta comercial — solo para orientar dónde está
   el problema.

5. Estacionalidad de Mar del Plata: si la pregunta P51 indica que la
   clínica declaró una época del año donde el negocio se complica, y
   estás interpretando el KPI 4 (no-show) o el KPI 12 (producción por
   hora-sillón) durante esa época, distinguí explícitamente un pico
   estacional de un problema estructural — no des el mismo diagnóstico
   que le darías a un mes normal.

6. Eje temporal — benchmark vs. historial propio: el payload trae
   `ponderacion` ({"benchmark": x, "historial": y}), calculada según
   cuántas semanas de datos propios tiene la clínica. Pesá tu
   interpretación según esos números: con `ponderacion.benchmark` alto
   (clínica recién arrancando), apoyate más en "comparado con la
   referencia (débil todavía)..."; con `ponderacion.historial` alto
   (clínica con línea base propia), apoyate más en la
   `serie_historica_propia` del payload: "tu propia tendencia: pasaste de
   X a Y, mejorando o empeorando" — la referencia externa pasa a segundo
   plano.

7. Nunca dictamines con más seguridad de la que los datos permiten. Si el
   contexto es insuficiente para explicar un gap, decilo así ("el número
   está bajo, pero no tengo contexto suficiente para saber por qué —
   habría que preguntar sobre X") en vez de inventar una causa.

8. Si el payload trae `diagnostico` (armado por diagnostico.py ANTES de
   esta llamada, no por vos): sus `contradicciones` y `patrones_cruzados`
   ya están verificados de forma determinista contra los datos — repetilos
   y explicalos en tu respuesta, no los vuelvas a derivar ni los
   contradigas. Su `estado` (HEALTHY/WATCH/PROBLEM/CRITICAL/
   INSUFFICIENT_EVIDENCE) te dice qué tan firme podés ser: nunca uses un
   tono más seguro que ese estado — INSUFFICIENT_EVIDENCE significa decir
   explícitamente que falta información, no inventar una causa igual.

Tu salida siempre tiene: (a) qué dice el número, (b) qué explica el
contexto cualitativo sobre ese número, (c) la conclusión — sea una causa
probable y una acción concreta, sea que hace falta más información.
"""


def interpretar_kpi(
    kpi_id: int,
    valor_clinica: float,
    respuestas_diagnostico: dict[str, str],
    semanas_de_datos_propios: Optional[int] = None,
    serie_historica: Optional[dict] = None,
    diagnostico=None,
    client=None,
) -> dict:
    """
    Interpreta un solo KPI: calcula el gap contra el benchmark argentino
    (si existe), lo cruza con el contexto cualitativo relevante para ese
    KPI, y pondera benchmark vs. historial propio según cuánto tiempo
    lleva la clínica generando sus propios datos.

    `serie_historica`: {período: valor} del propio KPI (lo arma
    coverage.evaluar_cobertura cuando todas sus variables traen serie —
    ver kpis_calculados[kpi_id]["serie"]). Si no se pasa
    `semanas_de_datos_propios` explícito, se deriva de esta serie en vez
    de asumir 0 — antes ningún llamador la calculaba, así que la
    ponderación siempre terminaba apoyándose al máximo en el benchmark
    externo (hallazgo 4).

    `diagnostico` (Fase 4, opcional — compatible hacia atrás con
    `client=None` en los tests): un `diagnostico.Diagnostico` ya calculado
    para este KPI. Si se pasa, sus contradicciones/patrones/estado viajan
    en el payload como hechos ya verificados (ver regla 8 del prompt) — el
    modelo no tiene que re-derivarlos desde cero.
    """
    if semanas_de_datos_propios is None:
        semanas_de_datos_propios = semanas_desde_serie(serie_historica)

    gap = calcular_gap(kpi_id, valor_clinica)
    contexto = construir_contexto_cualitativo(respuestas_diagnostico, kpi_id=kpi_id)
    ponderacion = peso_benchmark_vs_historial(semanas_de_datos_propios)
    kpi = KPI_BY_ID[kpi_id]

    payload = {
        "kpi": kpi.nombre,
        "valor_actual": valor_clinica,
        "valor_formateado": fmt_por_unidad(valor_clinica, kpi.unidad),
        "gap": _gap_a_dict(gap),
        "contexto_cualitativo": contexto,
        "ponderacion": ponderacion,
        "semanas_de_datos_propios": semanas_de_datos_propios,
        "serie_historica_propia": serie_historica or {},
        "diagnostico": _serializar_diagnostico(diagnostico),
    }

    if client is None:
        # Sin cliente configurado, devolvemos el payload crudo para poder
        # inspeccionar la lógica de gap + contexto sin llamar a la API.
        return {"payload_enviado_al_asistente": payload, "interpretacion": None, "truncado": False}

    respuesta = client.messages.create(
        model=MODEL,
        max_tokens=800,
        # Zoom a UN KPI ya calculado, con su gap y su contexto resueltos por
        # código: es redacción, no razonamiento. Sin esto corre thinking
        # adaptativo (default del modelo) y se come los 800 tokens.
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT_BASE,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
    )
    return {
        "payload_enviado_al_asistente": payload,
        "interpretacion": extraer_texto(respuesta),
        "truncado": respuesta_truncada(respuesta),
    }


def interpretar_panel(
    kpis_calculados: dict[int, dict],
    respuestas_diagnostico: dict[str, str],
    diagnostico=None,
    client=None,
) -> dict:
    """
    Interpreta TODO el panel en una sola llamada — a diferencia de
    `interpretar_kpi`, que solo ve un KPI a la vez y por diseño no puede
    cruzar nada (hallazgo 2 del informe de deficiencias: "el agente no
    relaciona métricas que podrían combinarse"). Acá el modelo recibe
    todos los KPIs ya calculados, su serie histórica, y el contexto
    cualitativo completo, y puede razonar sobre el conjunto — ej.
    aceptación alta + ticket bajo = problema de mix, no de cierre de venta.

    `kpis_calculados`: el dict que devuelve pipeline.procesar_migracion
    en "kpis_calculados" (kpi_id -> {"valor", "unidad", "confianza",
    "serie", ...}).

    `diagnostico` (Fase 4, opcional): la lista de `diagnostico.Diagnostico`
    que devuelve `diagnostico.diagnosticar()` — ya trae los patrones
    cruzados y contradicciones estructurados (regla 8 del prompt), así
    que el modelo no tiene que re-derivarlos desde el payload crudo.
    """
    contexto_general = construir_contexto_cualitativo(respuestas_diagnostico, kpi_id=None)

    kpis_payload = []
    for kpi_id, info in sorted(kpis_calculados.items()):
        valor = info.get("valor")
        serie = info.get("serie")
        ponderacion = peso_benchmark_vs_historial(semanas_desde_serie(serie))

        gap_dict = {"tiene_benchmark": False, "direccion": "no_aplica"}
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            gap_dict = _gap_a_dict(calcular_gap(kpi_id, valor))

        kpis_payload.append({
            "kpi_id": kpi_id,
            "nombre": info.get("nombre") or info.get("kpi_nombre") or KPI_BY_ID[kpi_id].nombre,
            "valor_actual": valor,
            "valor_formateado": fmt_por_unidad(valor, info.get("unidad", "")),
            "unidad": info.get("unidad"),
            "confianza": info.get("confianza"),
            "gap": gap_dict,
            "contexto_cualitativo": construir_contexto_cualitativo(respuestas_diagnostico, kpi_id=kpi_id),
            "ponderacion": ponderacion,
            "serie_historica_propia": serie or {},
        })

    payload = {
        "kpis": kpis_payload,
        "contexto_general": contexto_general,
        "diagnostico": _serializar_diagnostico(diagnostico),
    }

    if client is None:
        return {"payload_enviado_al_asistente": payload, "interpretacion": None, "truncado": False}

    respuesta = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        # Este es el que reventaba con "no tiene ningún bloque de texto":
        # omitir `thinking` corre adaptativo en Sonnet 5, y el thinking se
        # comía los 2000 tokens enteros. Los cruces entre KPIs que antes
        # justificaban razonar acá ya los resuelve diagnostico.py de forma
        # determinística y llegan en `payload["diagnostico"]` — este entry
        # point redacta sobre eso, no lo redescubre.
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT_BASE,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
    )
    return {
        "payload_enviado_al_asistente": payload,
        "interpretacion": extraer_texto(respuesta),
        "truncado": respuesta_truncada(respuesta),
    }


def _gap_a_dict(gap: Gap) -> dict:
    base = {"tiene_benchmark": gap.tiene_benchmark, "direccion": gap.direccion}
    if gap.benchmark is not None:
        # Metadata de la fuente se manda igual aunque no haya rango numérico
        # cargado (ej. KPI 12 y 15): sirve para que el asistente mencione el
        # proxy como orientación en vez de compararlo como si fuera un dato duro.
        base["confiabilidad_benchmark"] = gap.benchmark.confiabilidad
        base["fuente"] = gap.benchmark.fuente
        base["nota_benchmark"] = gap.benchmark.nota
    if gap.tiene_benchmark:
        base["favorable"] = gap.favorable
        base["magnitud_pct"] = gap.magnitud_pct
        base["rango_benchmark"] = [gap.benchmark.rango_bajo, gap.benchmark.rango_alto]
    return base


# ---------------------------------------------------------------------------
# Fase 7: interpretar_clinica — el tercer entry point (Tabla 4 del
# Documento Maestro: interpretar_kpi explica un indicador, interpretar_panel
# relaciona indicadores, interpretar_clinica construye el diagnóstico
# sistémico completo). Convive con los dos anteriores, no los reemplaza.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_CLINICA = """Sos el asistente de diagnóstico sistémico de Agencia IA
para clínicas dentales en Argentina. A diferencia de explicar un KPI o un
panel de KPIs, acá tu trabajo es construir el INFORME EJECUTIVO completo
de la clínica: no una lista de indicadores, sino qué está pasando, dónde
está el principal cuello de botella, por qué creemos que ocurre, y qué
intervención conviene implementar primero.

El payload que recibís ya viene estructurado por el Diagnostic Engine
(diagnostico.py) y el catálogo tecnológico (catalogo_tecnologico.py) — tu
trabajo es interpretar y redactar, NO descubrir la lógica de negocio
desde cero:
- `diagnosticos`: por cada KPI con problema, su estado
  (HEALTHY/NORMAL/WATCH/PROBLEM/CRITICAL/INSUFFICIENT_EVIDENCE), hechos,
  anomalías (con la confiabilidad del benchmark ya resuelta), hipótesis,
  contradicciones YA detectadas de forma determinista, y qué información falta.
- `oportunidades_priorizadas`: intervenciones reales del catálogo de
  Agencia IA, ya ordenadas por score (gap × impacto × confiabilidad ×
  addressability × suficiencia de datos).
- `calidad_datos`: completitud/consistencia/confianza del dato de base.

Reglas:

1. Nunca redimensiones ni contradigas lo que `diagnosticos[i].estado` ya
   dice. INSUFFICIENT_EVIDENCE significa decir "no hay evidencia
   suficiente", no inventar una causa igual.
2. Las `contradicciones` y `patrones_cruzados` de cada diagnóstico ya
   están verificados — repetilos y explicalos, no los vuelvas a derivar
   ni los contradigas.
3. Cada oportunidad tecnológica que menciones tiene que salir de
   `oportunidades_priorizadas` — nunca inventes una automatización o un
   proceso que no esté en esa lista (§13 del Documento Maestro: la
   tecnología es consecuencia del diagnóstico, no una moda).
4. Si `calidad_datos.completitud_pct` o `.confianza_promedio` son bajos,
   decilo explícitamente al principio del informe — el resto tiene que
   leerse con esa salvedad.
5. Separá SIEMPRE hechos confirmados, causas probables, e hipótesis — no
   los mezcles en la misma oración con el mismo tono de seguridad.

Estructura tu respuesta en estas 10 secciones, en este orden, texto plano
en español rioplatense, directo (no JSON):

1. RESUMEN EJECUTIVO — 3-4 líneas: situación general, principal cuello
   de botella, una fortaleza, la prioridad #1.
2. SALUD GENERAL DEL SISTEMA — visión del conjunto, no la suma de KPIs.
3. MAPA DEL FUNNEL — qué etapa (captación/conversión/confirmación/
   consulta/post-consulta/fidelización/referidos) está mejor y peor.
4. PRINCIPALES CUELLOS DE BOTELLA — 3 a 5, ordenados por prioridad.
5. EVIDENCIA — los KPIs y tendencias que sustentan cada cuello.
6. CAUSAS — separadas en confirmadas, probables, e hipótesis.
7. CONTRADICCIONES Y DATOS FALTANTES — dónde el dato no alcanza o
   contradice lo declarado.
8. OPORTUNIDADES TECNOLÓGICAS — solo de `oportunidades_priorizadas`, con
   su tipo (proceso/automatización/IA).
9. PLAN DE ACCIÓN — qué resolver primero y con qué se mide el éxito.
10. DETALLE DE KPIs — tabla breve de cada KPI relevante, como capa
    secundaria, no protagonista.
"""


def _payload_clinica(
    diagnosticos: list,
    oportunidades_priorizadas: list,
    calidad_datos,
    respuestas_diagnostico: dict[str, str],
    studio_nombre: Optional[str],
) -> dict:
    diagnosticos_payload = []
    for d in diagnosticos:
        diagnosticos_payload.append({
            "kpi_id": d.kpi_id,
            "problema": d.problema,
            "estado": d.estado,  # EstadoEvidencia(str, Enum): serializa como su propio string
            "hechos": d.hechos,
            "anomalias": [dataclasses.asdict(a) for a in d.anomalias],
            "hipotesis": [dataclasses.asdict(h) for h in d.hipotesis],
            "contradicciones": [dataclasses.asdict(c) for c in d.contradicciones],
            "patrones_cruzados": d.patrones_cruzados,
            "informacion_faltante": d.informacion_faltante,
            "confianza": d.confianza,
        })

    oportunidades_payload = []
    for o in oportunidades_priorizadas:
        intervencion = o.oportunidad.intervencion
        oportunidades_payload.append({
            "kpi_id": o.kpi_id,
            "score": o.score,
            "impacto": o.impacto,
            "addressability": o.oportunidad.addressability,
            "intervencion": {
                "nombre": intervencion.nombre,
                "tipo": intervencion.tipo,
                "etapa": intervencion.etapa,
                "metrica_objetivo": intervencion.metrica_objetivo,
                "condicion": intervencion.condicion,
                "requiere_compliance": intervencion.requiere_compliance,
            },
        })

    return {
        "studio_nombre": studio_nombre,
        "contexto_general": construir_contexto_cualitativo(respuestas_diagnostico, kpi_id=None),
        "diagnosticos": diagnosticos_payload,
        "oportunidades_priorizadas": oportunidades_payload,
        "calidad_datos": dataclasses.asdict(calidad_datos) if calidad_datos is not None else None,
    }


def interpretar_clinica(
    diagnosticos: list,
    oportunidades_priorizadas: list,
    calidad_datos=None,
    respuestas_diagnostico: Optional[dict[str, str]] = None,
    studio_nombre: Optional[str] = None,
    client=None,
) -> dict:
    """
    Tercer entry point (Tabla 4 del Documento Maestro): construye el
    informe jerárquico de 10 secciones a partir de lo que ya calcularon
    diagnostico.py + catalogo_tecnologico.py + priorizacion.py — nunca
    recalcula gaps ni redescubre patrones, solo interpreta y redacta.

    `diagnosticos`: lista de `diagnostico.Diagnostico` (ver
    `diagnostico.diagnosticar`). `oportunidades_priorizadas`: lista de
    `priorizacion.OportunidadPriorizada` (ver `priorizacion.priorizar_oportunidades`).
    `calidad_datos`: `calidad.ReporteCalidad` opcional (ver `calidad.evaluar_calidad`).

    Ambos parámetros llegan ya calculados — este módulo no importa
    diagnostico.py/catalogo_tecnologico.py/priorizacion.py para no crear
    una cadena de imports más larga de la que ya rompió el ciclo original
    (ver contexto_cualitativo.py); solo necesita que los objetos tengan
    los atributos esperados (duck typing vía dataclasses.asdict).
    """
    payload = _payload_clinica(
        diagnosticos, oportunidades_priorizadas, calidad_datos, respuestas_diagnostico or {}, studio_nombre,
    )

    if client is None:
        return {"payload_enviado_al_asistente": payload, "informe": None, "truncado": False}

    # Único entry point donde el thinking se justifica: un informe de 10
    # secciones que jerarquiza cuellos de botella y arma un plan de acción
    # sí es razonamiento, no redacción. Por eso acá va adaptativo — pero
    # declarado, no heredado del default — con presupuesto suficiente para
    # que el thinking NO se coma el informe (max_tokens es el techo de los
    # dos juntos), y en streaming, que es lo que evita el timeout HTTP del
    # SDK con max_tokens alto.
    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT_CLINICA,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
    ) as stream:
        respuesta = stream.get_final_message()
    return {
        "payload_enviado_al_asistente": payload,
        "informe": extraer_texto(respuesta),
        "truncado": respuesta_truncada(respuesta),
    }
