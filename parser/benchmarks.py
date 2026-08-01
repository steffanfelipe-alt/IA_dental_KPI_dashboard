"""
benchmarks.py

Estructura de benchmarks argentinos para los 13 KPIs comparables (los
otros 7 son financieros/internos — ver `SOLO_MIGRACION_O_SISTEMA` e
`INTERNAL_VARIABLES` en schema.py — dependen 100% del historial propio de
la clínica, nunca de un benchmark externo).

Fuente completa: `parser/referencias/benchmarks_research_AR.md` (research
en Gemini). Regla transversal: **nunca dar más precisión de la que el dato
permite** — 11 de 13 indicadores son proxy internacional o directamente
`sin_benchmark`; un benchmark inventado es peor que no tener benchmark,
porque el sistema lo usa para decirle a un dueño de clínica que está
perdiendo plata.

Dos casos especiales:
- KPI 6 (ticket promedio): `es_multiplo_arancel=True` — el rango está en
  múltiplos de "consulta" del arancel del Círculo, no en ARS fijo. Se
  resuelve a pesos acá mismo, contra `ARANCEL_COM["consulta"]` vigente.
- KPIs 12 y 15: tienen `confiabilidad` distinta de "sin_benchmark" (hay
  proxy internacional citable) pero `rango_bajo/alto = None` — no se
  cargó un número porque convertirlo a un rango accionable requeriría
  inventar un tipo de cambio (KPI 12) o tratar una estimación regional no
  auditada como si fuera una cifra dura (KPI 15). La `nota` explica el
  proxy igual, para que el asistente lo mencione como orientación.
"""

from dataclasses import dataclass
from typing import Optional

from aranceles_com import ARANCEL_COM


@dataclass
class BenchmarkKPI:
    kpi_id: int
    rango_bajo: Optional[float]
    rango_alto: Optional[float]
    unidad: str
    mejor_es: str = "mayor"             # "mayor" | "menor" — dirección deseada
    es_multiplo_arancel: bool = False   # True: rango_bajo/alto están en múltiplos de ARANCEL_COM["consulta"]
    fuente: str = ""
    fecha: str = ""
    confiabilidad: str = "sin_benchmark"  # "oficial" | "consultora_ar" | "proxy_internacional" | "sin_benchmark"
    nota: str = ""


BENCHMARKS_AR: dict[int, BenchmarkKPI] = {
    1: BenchmarkKPI(
        1, None, None, "conteo", mejor_es="mayor",
        confiabilidad="sin_benchmark",
        nota="Consultas nuevas/mes es un conteo crudo, no una tasa: no hay benchmark "
             "universal posible porque depende 100% del tamaño de la clínica "
             "(sillones, profesionales, horas de atención). Comparar contra la "
             "tendencia histórica propia, no contra un número externo.",
    ),
    2: BenchmarkKPI(
        2, 0, 5, "min", mejor_es="menor",
        fuente="Playmedic / Harvard Business Review (Oldroyd et al., 2011)",
        fecha="2011-2026", confiabilidad="proxy_internacional",
        nota="Ideal <2 min; a partir de 5 min se pierde el lead frente a otra clínica.",
    ),
    3: BenchmarkKPI(
        3, 35, 50, "%", mejor_es="mayor",
        fuente="Growlityc / Dental Economics",
        fecha="2026", confiabilidad="proxy_internacional",
        nota="35-50% con sistema de seguimiento automático; 15-25% sin sistema.",
    ),
    4: BenchmarkKPI(
        4, 8, 15, "%", mejor_es="menor",
        fuente="Nahuel Borel (Geblix) en La Nación 22/07/2021; Planet DDS 2025",
        fecha="2021-2025", confiabilidad="consultora_ar",
        nota="Típico actual en Argentina: 25-30%. Meta sana <15%, excelente <8%. "
             "Si supera 30% es prioridad operativa #1.",
    ),
    5: BenchmarkKPI(
        5, 65, 75, "%", mejor_es="mayor",
        fuente="Mola / Henry Schein One / Dental Intelligence-Levin Group",
        fecha="2021-2026", confiabilidad="proxy_internacional",
        nota="35-50% es el promedio general; 65-75% es el rango saludable. "
             "Cae fuerte en tratamientos de alto monto.",
    ),
    6: BenchmarkKPI(
        6, 1.5, 3.0, "consulta", mejor_es="mayor", es_multiplo_arancel=True,
        fuente="Círculo Odontológico de Mar del Plata, aranceles marzo 2025",
        fecha="2025-03", confiabilidad="oficial",
        nota="Ticket promedio ponderado ≈ 1.5-3 consultas según mix de tratamientos. "
             "Se compara en ARS contra ARANCEL_COM['consulta'] vigente.",
    ),
    7: BenchmarkKPI(
        7, None, None, "%", mejor_es="mayor",
        confiabilidad="sin_benchmark",
        nota="Sin dato argentino ni proxy internacional confiable para tasa de "
             "finalización de tratamientos multi-sesión. Usar tendencia propia.",
    ),
    8: BenchmarkKPI(
        8, 70, 80, "%", mejor_es="mayor",
        fuente="Kandent Tools / ImpulsoDent",
        fecha="2026", confiabilidad="proxy_internacional",
        nota="<60% es señal de fuga de base. Retener cuesta 5-25x menos que captar "
             "(Harvard Business Review / Bain & Company).",
    ),
    9: BenchmarkKPI(
        9, 15, 25, "%", mejor_es="mayor",
        fuente="Growlityc / Kandent Tools",
        fecha="2026", confiabilidad="proxy_internacional",
        nota="Umbral de 'inactivo' en odontología general ≈ 14 meses.",
    ),
    10: BenchmarkKPI(
        10, None, None, "%", mejor_es="mayor",
        confiabilidad="sin_benchmark",
        nota="No se halló un % estándar de reseñas/referidos sobre pacientes "
             "atendidos. Fijar meta propia (ej. de X a Y reseñas en 90 días).",
    ),
    12: BenchmarkKPI(
        12, None, None, "$/hora", mejor_es="mayor",
        fuente="ADA / Dental Economics / DentistryIQ",
        fecha="2025-2026", confiabilidad="proxy_internacional",
        nota="Proxy USD 350-600/hora (dentista general). Sin dato argentino en "
             "pesos ni tipo de cambio confiable para convertirlo: se deriva de "
             "ARANCEL_COM × turnos/hora reales de la clínica, no hay un rango "
             "fijo cargado acá (evita inventar una cifra).",
    ),
    13: BenchmarkKPI(
        13, 95, 100, "%", mejor_es="mayor",
        fuente="Mola / ADA",
        fecha="2026", confiabilidad="proxy_internacional",
        nota="Ojo con débitos/rechazos de obras sociales: el cobro privado ronda "
             "el 100%, el convenio es donde se pierde.",
    ),
    15: BenchmarkKPI(
        15, None, None, "hs/semana", mejor_es="menor",
        fuente="NM Tech Studio (Ecuador)",
        fecha="2026", confiabilidad="proxy_internacional",
        nota="~12 hs/persona/semana liberables con automatización — orden de "
             "magnitud regional (LatAm, no odontológico específico), NO cifra dura.",
    ),
    19: BenchmarkKPI(
        19, None, None, "$/paciente", mejor_es="menor",
        confiabilidad="sin_benchmark",
        nota="Sin dato argentino real en pesos. Único proxy hallado es de España "
             "(CAC 100-200 EUR en Google Ads), no comparable de forma confiable. "
             "Reactivar cuesta 5-7x menos que captar (dirección, no monto).",
    ),
}


@dataclass
class Gap:
    kpi_id: int
    valor_clinica: float
    benchmark: Optional[BenchmarkKPI]
    tiene_benchmark: bool
    direccion: str                  # "por_debajo" | "dentro_de_rango" | "por_encima" | "sin_benchmark"
    favorable: Optional[bool]       # True/False según mejor_es; None si no hay rango numérico
    magnitud_pct: Optional[float]   # qué tan lejos está del punto medio del rango, en %


def _rango_efectivo(benchmark: BenchmarkKPI) -> tuple[float, float]:
    """Resuelve rango_bajo/alto a la misma unidad de valor_clinica (ARS para es_multiplo_arancel)."""
    if not benchmark.es_multiplo_arancel:
        return benchmark.rango_bajo, benchmark.rango_alto
    valor_consulta = ARANCEL_COM["consulta"]
    return benchmark.rango_bajo * valor_consulta, benchmark.rango_alto * valor_consulta


def calcular_gap(kpi_id: int, valor_clinica: float) -> Gap:
    benchmark = BENCHMARKS_AR.get(kpi_id)

    if benchmark is None or benchmark.rango_bajo is None:
        return Gap(kpi_id, valor_clinica, benchmark, tiene_benchmark=False,
                    direccion="sin_benchmark", favorable=None, magnitud_pct=None)

    rango_bajo, rango_alto = _rango_efectivo(benchmark)
    mejor_es_mayor = benchmark.mejor_es == "mayor"

    if valor_clinica < rango_bajo:
        punto_medio = (rango_bajo + rango_alto) / 2
        magnitud = round(100 * (punto_medio - valor_clinica) / punto_medio, 1) if punto_medio else None
        direccion = "por_debajo"
        favorable = not mejor_es_mayor   # estar por debajo es bueno solo si "menor" es mejor
    elif valor_clinica > rango_alto:
        punto_medio = (rango_bajo + rango_alto) / 2
        magnitud = round(100 * (valor_clinica - punto_medio) / punto_medio, 1) if punto_medio else None
        direccion = "por_encima"
        favorable = mejor_es_mayor       # estar por encima es bueno solo si "mayor" es mejor
    else:
        direccion = "dentro_de_rango"
        magnitud = 0.0
        favorable = True

    return Gap(kpi_id, valor_clinica, benchmark, tiene_benchmark=True,
                direccion=direccion, favorable=favorable, magnitud_pct=magnitud)
