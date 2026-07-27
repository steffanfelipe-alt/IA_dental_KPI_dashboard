"""
priorizacion.py

El motor de priorización diagramado en el Miro (score = gap × impacto,
elige el top-3 de restricciones a atacar) no tenía código propio todavía
— solo existía como diagrama. Este módulo lo implementa con el único
cambio que pide el plan maestro de benchmarks: multiplicar por un
`factor_confiabilidad`, para que un gap enorme contra un proxy débil no
rankee por encima de un gap mediano contra un dato oficial o de
consultora argentina.

`impacto` (cuánto mueve el negocio resolver ese KPI) sigue siendo un
número que decide quien llama a este módulo — ese criterio de negocio
vive en el diseño del Miro, no se recalcula acá.

TODO: los KPIs `sin_benchmark` (7, 10, 19) no tienen `magnitud_pct` (no
hay rango contra el cual medir un gap), así que hoy su score siempre da 0
y nunca entran al top-3 por esta vía — el plan dice que esos se priorizan
"por tendencia propia", pero calcular un score numérico a partir de la
serie histórica (¿mejoró/empeoró, y cuánto?) es una extensión que este
plan no especificó en fórmula. Hasta entonces, esos 3 KPIs se priorizan
manualmente / vía la interpretación cualitativa (interpretacion.py), no
por este ranking.
"""

from dataclasses import dataclass

from benchmarks import Gap


FACTOR_CONFIABILIDAD = {
    "oficial": 1.0,
    "consultora_ar": 0.85,
    "proxy_internacional": 0.6,
    "sin_benchmark": 0.4,
}


@dataclass
class RestriccionPriorizada:
    kpi_id: int
    gap: Gap
    impacto: float
    score: float


def calcular_score(gap: Gap, impacto: float) -> float:
    """
    score = gap_normalizado × impacto × factor_confiabilidad

    gap_normalizado es 0 si el KPI está dentro de rango, sin benchmark, o
    el gap es en dirección favorable (ver Gap.favorable en benchmarks.py)
    — no tiene sentido "priorizar" arreglar algo que ya está bien.
    """
    if not gap.tiene_benchmark or gap.favorable or gap.magnitud_pct is None:
        gap_normalizado = 0.0
    else:
        gap_normalizado = min(gap.magnitud_pct / 100, 1.0)

    confiabilidad = gap.benchmark.confiabilidad if gap.benchmark is not None else "sin_benchmark"
    factor = FACTOR_CONFIABILIDAD.get(confiabilidad, FACTOR_CONFIABILIDAD["sin_benchmark"])
    return round(gap_normalizado * impacto * factor, 4)


def priorizar_kpis(gaps_con_impacto: list[tuple[Gap, float]], top_n: int = 3) -> list[RestriccionPriorizada]:
    """Ordena por score descendente y devuelve las top_n restricciones a atacar primero."""
    restricciones = [
        RestriccionPriorizada(gap.kpi_id, gap, impacto, calcular_score(gap, impacto))
        for gap, impacto in gaps_con_impacto
    ]
    return sorted(restricciones, key=lambda r: r.score, reverse=True)[:top_n]
