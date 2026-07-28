"""
calidad.py

Fase 3 del plan de evolución: Data Quality Report. El Documento Maestro
pide que la calidad del dato afecte explícitamente la confianza del
diagnóstico — esto es pura agregación de señales que YA existen en el
payload de `pipeline.procesar_migracion` (cuarentena, discrepancias de
reconciliación, confianza por variable, KPIs con error o en conflicto).
Cero extracción nueva: si hiciera falta llamar a Claude para esto, algo
estaría mal diseñado.

`suficiencia_datos` es el insumo que la Fase 6 (priorización extendida)
necesita como factor del score: un KPI armado 100% con variables
observadas es más confiable que uno donde parte se despejó de una tasa
declarada (`derivacion.py`) — la derivación es una defensa razonable, no
lo mismo que un dato leído directo.
"""

from dataclasses import dataclass
from typing import Optional

from reconciliacion import FUENTE_DERIVADA
from schema import KPI_BY_ID, KPI_FORMULAS


@dataclass
class ReporteCalidad:
    completitud_pct: float
    consistencia_pct: float
    confianza_promedio: Optional[float]  # None si no hay ninguna variable aceptada todavía
    datos_en_cuarentena: int
    kpis_afectados: list[int]


def _kpis_afectados_por_cuarentena(variables_en_cuarentena: dict) -> set[int]:
    vars_en_cuarentena = set(variables_en_cuarentena)
    return {kpi.id for kpi in KPI_FORMULAS if vars_en_cuarentena & set(kpi.variables)}


def _consistencia_pct(variables: dict, variables_en_cuarentena: dict, discrepancias: list) -> float:
    """% de lo que se intentó extraer que resultó consistente. Sin ningún
    intento (ni aceptado ni rechazado) no hay nada inconsistente que
    reportar — no es lo mismo que "faltan datos" (eso lo mide completitud)."""
    intentos = len(variables) + len(variables_en_cuarentena)
    if intentos == 0:
        return 100.0
    problemas = len(variables_en_cuarentena) + len(discrepancias)
    return round(100 * max(0.0, 1 - problemas / intentos), 1)


def evaluar_calidad(resultado_pipeline: dict) -> ReporteCalidad:
    """Lee el payload que devuelve `pipeline.procesar_migracion` — no
    vuelve a tocar ningún extractor ni la API de Claude."""
    kpis_calculados = resultado_pipeline.get("kpis_calculados") or {}
    kpis_bloqueados = resultado_pipeline.get("kpis_bloqueados_por_diseno") or []
    kpis_con_error = resultado_pipeline.get("kpis_con_error") or {}
    kpis_esperando_conflicto = resultado_pipeline.get("kpis_esperando_resolucion_conflicto") or {}
    variables_en_cuarentena = resultado_pipeline.get("variables_en_cuarentena") or {}
    discrepancias = resultado_pipeline.get("discrepancias_reconciliacion") or []
    variables = resultado_pipeline.get("variables") or {}

    # Los KPIs bloqueados por diseño (variables internas, ej. 16 y 17)
    # nunca dependen de un archivo ni de una respuesta del wizard — contar
    # su ausencia como "incompleto" penalizaría a toda clínica sin motivo,
    # así que se excluyen del denominador.
    kpis_relevantes = len(KPI_FORMULAS) - len(kpis_bloqueados)
    completitud = round(100 * len(kpis_calculados) / kpis_relevantes, 1) if kpis_relevantes else 0.0

    confianzas = [vv.confianza for vv in variables.values()]
    confianza_promedio = round(100 * sum(confianzas) / len(confianzas), 1) if confianzas else None

    kpis_afectados = sorted(
        set(kpis_con_error) | set(kpis_esperando_conflicto) | _kpis_afectados_por_cuarentena(variables_en_cuarentena)
    )

    return ReporteCalidad(
        completitud_pct=completitud,
        consistencia_pct=_consistencia_pct(variables, variables_en_cuarentena, discrepancias),
        confianza_promedio=confianza_promedio,
        datos_en_cuarentena=len(variables_en_cuarentena),
        kpis_afectados=kpis_afectados,
    )


def suficiencia_datos(kpi_id: int, variables: dict) -> Optional[float]:
    """Qué fracción de las variables de este KPI vienen de una fuente
    OBSERVADA (no derivada de una tasa — ver derivacion.py). 1.0 si todas
    son observadas; None si el KPI no está calculable con lo que hay
    (faltan variables) — no tiene sentido hablar de "suficiencia" de algo
    que ni siquiera se pudo calcular."""
    kpi = KPI_BY_ID.get(kpi_id)
    if kpi is None:
        return None
    requeridas = kpi.variables
    if any(v not in variables for v in requeridas):
        return None
    observadas = sum(1 for v in requeridas if variables[v].fuente != FUENTE_DERIVADA)
    return round(observadas / len(requeridas), 3)
