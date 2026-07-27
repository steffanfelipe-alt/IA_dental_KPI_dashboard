"""
schema.py

Vocabulario común de variables + las 20 fórmulas de KPIs.

Esta es la pieza central de todo el parser: en vez de que cada KPI defina
su propia forma de leer datos, todo (wizard, migración de Excel, fotos,
facturas automáticas) escribe al MISMO diccionario de variables. Las 20
fórmulas leen de ahí. Esto es lo que permite el chequeo de cobertura "por
variable, no por KPI" que se decidió en el diseño del onboarding: dos KPIs
que comparten una variable (ej. consultas_nuevas_mes) nunca la piden dos
veces.

Corresponde 1:1 a la tabla "6 · Fórmulas de los 20 KPIs" del Miro.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# 1. Vocabulario de variables base
# ---------------------------------------------------------------------------
# Cada variable tiene un tipo esperado y, cuando aplica, una unidad.
# "scalar_period" = un número por período (mes/semana) que se acumula en
# kpi_snapshots. "dict" = desglose por categoría (tratamiento, paciente).

VARIABLE_TYPES = {
    # --- Embudo ---
    "consultas_nuevas_mes": "int",
    "turnos_agendados": "int",
    "no_shows": "int",
    "presupuestos_emitidos": "int",
    "presupuestos_aceptados": "int",
    "monto_presupuestos_aceptados": "float",       # $ acumulado
    "tratamientos_iniciados": "int",
    "tratamientos_completados": "int",
    "pacientes_dados_alta": "int",
    "pacientes_vuelven_control": "int",
    "pacientes_inactivos_contactados": "int",
    "pacientes_reactivados": "int",
    "pacientes_atendidos_periodo": "int",
    "resenas_nuevas": "int",
    "referidos_nuevos": "int",

    # --- Financieras ---
    "monto_cobrado": "float",
    "monto_facturado": "float",
    "gasto_captacion": "float",
    "pacientes_nuevos_captados": "int",
    "gasto_reactivacion": "float",
    "ingreso_por_paciente": "dict",     # {paciente_id: monto histórico}
    "ingreso_por_tratamiento": "dict",  # {tipo_tratamiento: ingreso}
    "costo_por_tratamiento": "dict",    # {tipo_tratamiento: costo insumos}
    "costo_hora_sillon": "float",
    "duracion_tratamiento_horas": "dict",  # {tipo_tratamiento: horas}

    # --- Operativas ---
    "horas_sillon_ocupadas": "float",
    "tiempo_respuesta_promedio_min": "float",
    "horas_tarea_manual_semana": "dict",   # {tarea: horas/semana}
    "tareas_sin_backup": "list",           # [{tarea, responsable}, ...]

    # --- Internas (no vienen de migración ni wizard, las calcula el sistema) ---
    "automatizaciones_activas": "int",
    "tareas_manuales_detectadas": "int",
    "horas_semana_serie_historica": "list",  # [(fecha, horas), ...]
}

INTERNAL_VARIABLES = {
    "automatizaciones_activas",
    "tareas_manuales_detectadas",
    "horas_semana_serie_historica",
}

# Variables que, por diseño, nunca se preguntan en el wizard — ningún dueño
# da estos números de memoria de forma confiable. Solo llegan por migración
# de facturas o carga numérica directa desde el sistema (agenda, gastos).
# Corresponde a los 7 KPIs marcados "Gap financiero" en la tabla del Miro.
SOLO_MIGRACION_O_SISTEMA = {
    "monto_cobrado",
    "monto_facturado",
    "gasto_captacion",
    "gasto_reactivacion",
    "ingreso_por_paciente",
    "ingreso_por_tratamiento",
    "costo_por_tratamiento",
    "costo_hora_sillon",
    "duracion_tratamiento_horas",
    "horas_sillon_ocupadas",
}


@dataclass
class KPIFormula:
    id: int
    nombre: str
    variables: list[str]
    calcular: Callable[[dict], Optional[float]]
    unidad: str = "%"
    nota: str = ""


def _pct(numerador: float, denominador: float) -> Optional[float]:
    if not denominador:
        return None
    return round(100 * numerador / denominador, 1)


# ---------------------------------------------------------------------------
# 2. Las 20 fórmulas — cada una lee del dict de variables normalizadas
# ---------------------------------------------------------------------------

KPI_FORMULAS: list[KPIFormula] = [
    KPIFormula(1, "Consultas nuevas / mes",
               ["consultas_nuevas_mes"],
               lambda v: v["consultas_nuevas_mes"], unidad="conteo"),

    KPIFormula(2, "Tiempo de 1ª respuesta",
               ["tiempo_respuesta_promedio_min"],
               lambda v: v["tiempo_respuesta_promedio_min"], unidad="min"),

    KPIFormula(3, "Tasa de agendamiento",
               ["turnos_agendados", "consultas_nuevas_mes"],
               lambda v: _pct(v["turnos_agendados"], v["consultas_nuevas_mes"])),

    KPIFormula(4, "Tasa de no-show",
               ["no_shows", "turnos_agendados"],
               lambda v: _pct(v["no_shows"], v["turnos_agendados"])),

    KPIFormula(5, "Tasa de aceptación de presupuestos",
               ["presupuestos_aceptados", "presupuestos_emitidos"],
               lambda v: _pct(v["presupuestos_aceptados"], v["presupuestos_emitidos"])),

    KPIFormula(6, "Ticket promedio",
               ["monto_presupuestos_aceptados", "presupuestos_aceptados"],
               lambda v: round(v["monto_presupuestos_aceptados"] / v["presupuestos_aceptados"], 2)
               if v["presupuestos_aceptados"] else None,
               unidad="$"),

    KPIFormula(7, "Tasa de finalización de tratamiento",
               ["tratamientos_completados", "tratamientos_iniciados"],
               lambda v: _pct(v["tratamientos_completados"], v["tratamientos_iniciados"])),

    KPIFormula(8, "Recall / retención",
               ["pacientes_vuelven_control", "pacientes_dados_alta"],
               lambda v: _pct(v["pacientes_vuelven_control"], v["pacientes_dados_alta"])),

    KPIFormula(9, "Tasa de reactivación",
               ["pacientes_reactivados", "pacientes_inactivos_contactados"],
               lambda v: _pct(v["pacientes_reactivados"], v["pacientes_inactivos_contactados"])),

    KPIFormula(10, "Tasa de reseñas / referidos",
               ["resenas_nuevas", "referidos_nuevos", "pacientes_atendidos_periodo"],
               lambda v: _pct(v["resenas_nuevas"] + v["referidos_nuevos"], v["pacientes_atendidos_periodo"])),

    KPIFormula(11, "Throughput (ingresos cobrados)",
               ["monto_cobrado"],
               lambda v: v["monto_cobrado"], unidad="$"),

    KPIFormula(12, "Producción por hora-sillón",
               ["monto_cobrado", "horas_sillon_ocupadas"],
               lambda v: round(v["monto_cobrado"] / v["horas_sillon_ocupadas"], 2)
               if v["horas_sillon_ocupadas"] else None,
               unidad="$/hora"),

    KPIFormula(13, "Tasa de cobro",
               ["monto_cobrado", "monto_facturado"],
               lambda v: _pct(v["monto_cobrado"], v["monto_facturado"])),

    KPIFormula(14, "Valor del paciente (LTV)",
               ["ingreso_por_paciente"],
               lambda v: round(sum(v["ingreso_por_paciente"].values()) / len(v["ingreso_por_paciente"]), 2)
               if v["ingreso_por_paciente"] else None,
               unidad="$"),

    KPIFormula(15, "Horas/semana en tareas repetitivas",
               ["horas_tarea_manual_semana"],
               lambda v: round(sum(v["horas_tarea_manual_semana"].values()), 1),
               unidad="hs/semana"),

    KPIFormula(16, "% de tareas repetitivas ya automatizadas",
               ["automatizaciones_activas", "tareas_manuales_detectadas"],
               lambda v: _pct(v["automatizaciones_activas"], v["tareas_manuales_detectadas"])),

    KPIFormula(17, "Horas-persona liberadas / mes",
               ["horas_semana_serie_historica"],
               lambda v: _horas_liberadas(v["horas_semana_serie_historica"]),
               unidad="hs/mes"),

    KPIFormula(18, "Tareas que dependen de una sola persona",
               ["tareas_sin_backup"],
               lambda v: len(v["tareas_sin_backup"]), unidad="conteo"),

    KPIFormula(19, "Costo adquisición vs. reactivación",
               ["gasto_captacion", "pacientes_nuevos_captados", "gasto_reactivacion", "pacientes_reactivados"],
               lambda v: {
                   "costo_adquisicion": round(v["gasto_captacion"] / v["pacientes_nuevos_captados"], 2)
                   if v["pacientes_nuevos_captados"] else None,
                   "costo_reactivacion": round(v["gasto_reactivacion"] / v["pacientes_reactivados"], 2)
                   if v["pacientes_reactivados"] else None,
               }, unidad="$/paciente"),

    KPIFormula(20, "Rentabilidad por tratamiento",
               ["ingreso_por_tratamiento", "costo_por_tratamiento", "costo_hora_sillon", "duracion_tratamiento_horas"],
               lambda v: _rentabilidad_por_tratamiento(v), unidad="$"),
]


def _horas_liberadas(serie: list) -> Optional[float]:
    """Compara el primer y el último punto de la serie histórica de horas/semana."""
    if len(serie) < 2:
        return None
    horas_antes = serie[0][1]
    horas_despues = serie[-1][1]
    return round((horas_antes - horas_despues) * 4.33, 1)


def _rentabilidad_por_tratamiento(v: dict) -> Optional[dict]:
    ingresos = v["ingreso_por_tratamiento"]
    costos = v["costo_por_tratamiento"]
    costo_hora = v["costo_hora_sillon"]
    duraciones = v["duracion_tratamiento_horas"]
    if not ingresos:
        return None
    resultado = {}
    for tipo, ingreso in ingresos.items():
        costo_insumos = costos.get(tipo, 0)
        horas = duraciones.get(tipo, 0)
        resultado[tipo] = round(ingreso - (costo_insumos + costo_hora * horas), 2)
    return resultado


KPI_BY_ID = {k.id: k for k in KPI_FORMULAS}
