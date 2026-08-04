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

TODO: los KPIs `sin_benchmark` (1, 7, 10, 19) no tienen `magnitud_pct` (no
hay rango contra el cual medir un gap), así que hoy su score siempre da 0
y nunca entran al top-3 por esta vía — el plan dice que esos se priorizan
"por tendencia propia", pero calcular un score numérico a partir de la
serie histórica (¿mejoró/empeoró, y cuánto?) es una extensión que este
plan no especificó en fórmula. Hasta entonces, esos 4 KPIs se priorizan
manualmente / vía la interpretación cualitativa (interpretacion.py), no
por este ranking.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from parser.diagnostico.benchmarks import Gap

if TYPE_CHECKING:  # evita acoplar priorizacion.py a diagnostico.py/catalogo_tecnologico.py en runtime
    from parser.catalogo.catalogo_tecnologico import Oportunidad
    from parser.diagnostico.diagnostico import Diagnostico


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


def _score_desde_partes(
    magnitud_pct: Optional[float], favorable: bool, tiene_benchmark: bool, confiabilidad: str,
    impacto: float, addressability: float = 1.0, suficiencia: float = 1.0,
) -> float:
    """La aritmética real del score, separada de `calcular_score` para que
    también la pueda usar `calcular_score_diagnostico` (Fase 6) sin
    necesitar un `benchmarks.Gap` completo — un `diagnostico.Diagnostico`
    ya trae `magnitud_pct`/`confiabilidad_benchmark` en su `Anomalia`, no
    el Gap crudo."""
    if not tiene_benchmark or favorable or magnitud_pct is None:
        gap_normalizado = 0.0
    else:
        gap_normalizado = min(magnitud_pct / 100, 1.0)
    factor = FACTOR_CONFIABILIDAD.get(confiabilidad, FACTOR_CONFIABILIDAD["sin_benchmark"])
    return round(gap_normalizado * impacto * factor * addressability * suficiencia, 4)


def calcular_score(gap: Gap, impacto: float, addressability: float = 1.0, suficiencia: float = 1.0) -> float:
    """
    score = gap_normalizado × impacto × factor_confiabilidad × addressability × suficiencia

    gap_normalizado es 0 si el KPI está dentro de rango, sin benchmark, o
    el gap es en dirección favorable (ver Gap.favorable en benchmarks.py)
    — no tiene sentido "priorizar" arreglar algo que ya está bien.

    `addressability` y `suficiencia` (Fase 6, default 1.0 — no rompen
    ninguna llamada existente): un problema grande pero sin ninguna
    intervención entregable (addressability baja) o medido con una
    variable derivada (suficiencia baja) no debería rankear por encima de
    uno mediano con un camino de solución claro y datos observados.
    """
    confiabilidad = gap.benchmark.confiabilidad if gap.benchmark is not None else "sin_benchmark"
    return _score_desde_partes(
        gap.magnitud_pct, gap.favorable, gap.tiene_benchmark, confiabilidad,
        impacto, addressability, suficiencia,
    )


def calcular_score_diagnostico(diagnostico: "Diagnostico", impacto: float, addressability: float = 1.0) -> float:
    """Igual que `calcular_score`, pero a partir de un `diagnostico.Diagnostico`
    en vez de un `Gap` crudo — es lo que permite cablear priorizacion.py
    contra la salida real de diagnostico.py (antes de la Fase 6, este
    módulo no lo llamaba nadie en producción). `suficiencia` se toma de
    `diagnostico.confianza` (Fase 3), no hace falta pasarla aparte."""
    if not diagnostico.anomalias:
        return 0.0  # HEALTHY o INSUFFICIENT_EVIDENCE: nada que priorizar
    anomalia = diagnostico.anomalias[0]
    tiene_benchmark = anomalia.confiabilidad_benchmark != "sin_benchmark"
    return _score_desde_partes(
        anomalia.magnitud_pct, favorable=False, tiene_benchmark=tiene_benchmark,
        confiabilidad=anomalia.confiabilidad_benchmark, impacto=impacto,
        addressability=addressability, suficiencia=diagnostico.confianza,
    )


def priorizar_kpis(gaps_con_impacto: list[tuple[Gap, float]], top_n: int = 3) -> list[RestriccionPriorizada]:
    """Ordena por score descendente y devuelve las top_n restricciones a atacar primero."""
    restricciones = [
        RestriccionPriorizada(gap.kpi_id, gap, impacto, calcular_score(gap, impacto))
        for gap, impacto in gaps_con_impacto
    ]
    return sorted(restricciones, key=lambda r: r.score, reverse=True)[:top_n]


@dataclass
class OportunidadPriorizada:
    kpi_id: int
    oportunidad: "Oportunidad"
    impacto: float
    score: float


def priorizar_oportunidades(
    oportunidades: list["Oportunidad"], impacto_por_kpi: dict[int, float], top_n: int = 3,
) -> list[OportunidadPriorizada]:
    """Cablea diagnostico.py + catalogo_tecnologico.py contra el motor de
    priorización: cada `Oportunidad` (catalogo_tecnologico.mapear_oportunidades)
    ya trae su `addressability` calculada contra el contexto real de la
    clínica, y su `.diagnostico.confianza` es la suficiencia de datos —
    acá solo falta `impacto`, que sigue siendo un criterio de negocio que
    decide quien llama (no se recalcula acá, igual que en `priorizar_kpis`)."""
    restricciones = [
        OportunidadPriorizada(
            kpi_id=o.kpi_id,
            oportunidad=o,
            impacto=impacto_por_kpi.get(o.kpi_id, 1.0),
            score=calcular_score_diagnostico(
                o.diagnostico, impacto_por_kpi.get(o.kpi_id, 1.0), addressability=o.addressability,
            ),
        )
        for o in oportunidades
    ]
    return sorted(restricciones, key=lambda r: r.score, reverse=True)[:top_n]
