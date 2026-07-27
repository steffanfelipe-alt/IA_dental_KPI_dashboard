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

import json
from typing import Optional

from schema import KPI_BY_ID
from benchmarks import calcular_gap, Gap

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


MODEL = "claude-sonnet-5"

# Preguntas de la Guía de Diagnóstico que son puramente cualitativas — no
# alimentan ninguna fórmula, pero sí dan contexto para interpretar los
# números. Mapeadas a qué bloque/tema tocan, para poder filtrar cuáles
# son relevantes según qué KPI se está interpretando.
#
# P51 ("¿hay una época del año donde esto se complica?") está conectada a
# los KPIs 4 (no-show) y 12 (producción por sillón) a propósito: Mar del
# Plata tiene estacionalidad turística fuerte, y sin ese contexto el
# asistente no puede distinguir un pico estacional de un problema
# estructural (ver regla 6 del system prompt).
CONTEXTO_CUALITATIVO_POR_KPI: dict[int, list[str]] = {
    3:  ["P1", "P37"],                          # tasa de agendamiento <- cómo agendan, tiempo de respuesta
    4:  ["P1", "P2", "P5", "P6", "P7", "P51"],  # no-show <- confirmación, lista de espera, agenda duplicada, estacionalidad
    5:  ["P19", "P20", "P23"],                  # aceptación de presupuestos <- cómo presentan, si hacen seguimiento
    6:  ["P19", "P24", "P25"],                  # ticket promedio <- cómo arman presupuesto, financiación
    7:  ["P22"],                                # finalización <- qué pasa si el paciente deja de venir
    8:  ["P40", "P42"],                         # recall <- si hacen seguimiento post-tratamiento
    9:  ["P42", "P43"],                         # reactivación <- relación con pacientes que dejan de venir
    10: ["P41"],                                # reseñas <- si piden reseñas y de qué forma
    12: ["P29", "P30", "P51"],                  # producción por sillón <- reprogramaciones, estacionalidad
    13: ["P24", "P26", "P27"],                  # tasa de cobro <- medios de cobro, pagos atrasados, integración
    15: ["P8", "P9", "P28"],                    # horas en tareas repetitivas <- qué tan manual es cada proceso
    19: ["P36", "P38"],                         # costo adquisición <- de dónde vienen los pacientes hoy
}

# Preguntas que dan contexto general de toda la clínica, sin importar qué
# KPI se esté mirando (calificación, estacionalidad, riesgo, tecnología).
CONTEXTO_GENERAL = ["P32", "P33", "P34", "P44", "P45", "P46", "P48", "P49", "P50", "P51", "P52", "P53"]


def construir_contexto_cualitativo(
    respuestas_diagnostico: dict[str, str],
    kpi_id: Optional[int] = None,
) -> str:
    """
    Arma un resumen legible de las respuestas cualitativas relevantes.
    Si se pasa un kpi_id, prioriza las preguntas de ese KPI + el contexto
    general; si no, devuelve todo lo disponible.
    """
    preguntas_relevantes = list(CONTEXTO_GENERAL)
    if kpi_id is not None:
        preguntas_relevantes = CONTEXTO_CUALITATIVO_POR_KPI.get(kpi_id, []) + preguntas_relevantes

    lineas = []
    for p in preguntas_relevantes:
        if p in respuestas_diagnostico:
            lineas.append(f"- {p}: {respuestas_diagnostico[p]}")

    if not lineas:
        return "(sin respuestas cualitativas cargadas todavía para este contexto)"
    return "\n".join(lineas)


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
   (clínica con línea base propia), apoyate más en la `serie_historica`
   del payload: "tu propia tendencia: pasaste de X a Y, mejorando o
   empeorando" — la referencia externa pasa a segundo plano.

7. Nunca dictamines con más seguridad de la que los datos permiten. Si el
   contexto es insuficiente para explicar un gap, decilo así ("el número
   está bajo, pero no tengo contexto suficiente para saber por qué —
   habría que preguntar sobre X") en vez de inventar una causa.

Tu salida siempre tiene: (a) qué dice el número, (b) qué explica el
contexto cualitativo sobre ese número, (c) la conclusión — sea una causa
probable y una acción concreta, sea que hace falta más información.
"""


def interpretar_kpi(
    kpi_id: int,
    valor_clinica: float,
    respuestas_diagnostico: dict[str, str],
    semanas_de_datos_propios: int = 0,
    serie_historica: Optional[list] = None,
    client=None,
) -> dict:
    """
    Interpreta un solo KPI: calcula el gap contra el benchmark argentino
    (si existe), lo cruza con el contexto cualitativo relevante para ese
    KPI, y pondera benchmark vs. historial propio según cuánto tiempo
    lleva la clínica generando sus propios datos.
    """
    gap = calcular_gap(kpi_id, valor_clinica)
    contexto = construir_contexto_cualitativo(respuestas_diagnostico, kpi_id=kpi_id)
    ponderacion = peso_benchmark_vs_historial(semanas_de_datos_propios)

    payload = {
        "kpi": KPI_BY_ID[kpi_id].nombre,
        "valor_actual": valor_clinica,
        "gap": _gap_a_dict(gap),
        "contexto_cualitativo": contexto,
        "ponderacion": ponderacion,
        "semanas_de_datos_propios": semanas_de_datos_propios,
        "serie_historica_propia": serie_historica or [],
    }

    if client is None:
        # Sin cliente configurado, devolvemos el payload crudo para poder
        # inspeccionar la lógica de gap + contexto sin llamar a la API.
        return {"payload_enviado_al_asistente": payload, "interpretacion": None}

    respuesta = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=SYSTEM_PROMPT_BASE,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
    )
    return {"payload_enviado_al_asistente": payload, "interpretacion": respuesta.content[0].text}


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
