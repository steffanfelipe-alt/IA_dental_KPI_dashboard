"""
contexto_cualitativo.py

Extraído de interpretacion.py (Fase 4) para romper un import circular:
diagnostico.py necesita este contexto para armar hipótesis, e
interpretacion.py necesita el diagnóstico de diagnostico.py — si esto se
quedaba en interpretacion.py, los dos módulos terminaban importándose
mutuamente. `interpretacion.py` re-exporta estos nombres para no romper a
nadie que ya los importaba desde ahí (ver test_benchmarks.py).

Preguntas de la Guía de Diagnóstico que son puramente cualitativas — no
alimentan ninguna fórmula, pero sí dan contexto para interpretar los
números. Mapeadas a qué bloque/tema tocan, para poder filtrar cuáles son
relevantes según qué KPI se está interpretando.

P51 ("¿hay una época del año donde esto se complica?") está conectada a
los KPIs 4 (no-show) y 12 (producción por sillón) a propósito: Mar del
Plata tiene estacionalidad turística fuerte, y sin ese contexto no se
puede distinguir un pico estacional de un problema estructural (ver
estacionalidad.py, Fase 4, y la regla 5 de interpretacion.SYSTEM_PROMPT_BASE).
"""

from typing import Optional

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
