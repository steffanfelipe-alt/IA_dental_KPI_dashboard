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


@dataclass
class MetricaInfo:
    """Definición completa de una variable para dársela a un extractor.

    El nombre de la variable solo ("horas_tarea_manual_semana") no alcanza
    para que un extractor no la confunda con una vecina parecida — el
    informe de deficiencias documentó justamente eso (hallazgo 1.3):
    tiempo_respuesta_promedio_min, tareas_sin_backup y
    automatizaciones_activas terminaron con el mismo valor porque el
    prompt solo tenía la lista pelada de nombres.
    """
    nombre_humano: str
    definicion: str
    unidad_dato: str              # unidad que debe tener el NÚMERO extraído
    sinonimos: list[str] = field(default_factory=list)
    no_confundir_con: str = ""


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


# ---------------------------------------------------------------------------
# 1b. Diccionario de métricas — una entrada por variable de VARIABLE_TYPES,
#     con definición completa para que un extractor (Excel o visión) no
#     tenga que "adivinar" a qué variable corresponde una columna o una
#     fila parecida a otra.
# ---------------------------------------------------------------------------

METRICAS: dict[str, MetricaInfo] = {
    "consultas_nuevas_mes": MetricaInfo(
        "Consultas nuevas por mes",
        "Cantidad de leads/consultas NUEVAS (primer contacto de un paciente "
        "que nunca contactó antes) que recibe la clínica en el período. Un "
        "CONTEO de personas, no una tasa ni un porcentaje.",
        "conteo",
        sinonimos=["consultas nuevas", "leads nuevos", "contactos nuevos", "consultas entrantes"],
        no_confundir_con="turnos_agendados (ya agendaron un turno) y pacientes_atendidos_periodo (ya fueron atendidos)",
    ),
    "turnos_agendados": MetricaInfo(
        "Turnos agendados",
        "Cantidad de turnos que se agendaron en el período, sin importar si "
        "el paciente asistió o no. Un CONTEO, no la tasa de agendamiento (esa "
        "tasa es turnos_agendados / consultas_nuevas_mes, y la calcula el sistema).",
        "conteo",
        sinonimos=["turnos agendados", "citas agendadas", "1er turno"],
        no_confundir_con="una columna llamada 'Tasa agenda' o similar (eso es un % ya calculado, NO este conteo)",
    ),
    "no_shows": MetricaInfo(
        "No-shows (ausencias sin aviso)",
        "Cantidad de turnos agendados a los que el paciente NO asistió. Un "
        "CONTEO de turnos, nunca un porcentaje. Si la hoja trae una columna "
        "de 'asistieron' y otra de 'agendados', no_shows = agendados - asistieron.",
        "conteo",
        sinonimos=["ausencias", "no asistió", "faltas"],
        no_confundir_con=(
            "una columna llamada 'Tasa no-show', '% no-show' o similar — esa es "
            "no_shows/turnos_agendados ya calculado como fracción o porcentaje, "
            "NO el conteo. Mapear esa columna acá es el error más común."
        ),
    ),
    "presupuestos_emitidos": MetricaInfo(
        "Presupuestos emitidos",
        "Cantidad de presupuestos/planes de tratamiento que la clínica le "
        "presentó a un paciente en el período, hayan sido aceptados o no.",
        "conteo",
        sinonimos=["presupuestos entregados", "planes presentados", "presupuestos presentados"],
        no_confundir_con="presupuestos_aceptados (subconjunto de estos)",
    ),
    "presupuestos_aceptados": MetricaInfo(
        "Presupuestos aceptados",
        "Cantidad de esos presupuestos que el paciente aceptó (firmó, dijo "
        "que sí). Siempre <= presupuestos_emitidos.",
        "conteo",
        sinonimos=["presupuestos aprobados", "planes aceptados"],
        no_confundir_con="una tasa de aceptación ya calculada (esa es %, no conteo)",
    ),
    "monto_presupuestos_aceptados": MetricaInfo(
        "Monto total de presupuestos aceptados",
        "Suma en ARS de todos los presupuestos aceptados en el período "
        "(no el monto cobrado todavía, solo lo presupuestado y aceptado).",
        "monto_ars",
        sinonimos=["monto presupuestado aceptado", "total presupuestos aceptados"],
        no_confundir_con="monto_cobrado (lo efectivamente cobrado) ni monto_facturado",
    ),
    "tratamientos_iniciados": MetricaInfo(
        "Tratamientos iniciados",
        "Cantidad de tratamientos de varias sesiones que arrancaron en el período.",
        "conteo",
        sinonimos=["tratamientos comenzados", "planes iniciados"],
    ),
    "tratamientos_completados": MetricaInfo(
        "Tratamientos completados",
        "Cantidad de esos tratamientos que efectivamente se terminaron.",
        "conteo",
        sinonimos=["tratamientos finalizados", "tratamientos terminados"],
        no_confundir_con="tratamientos_iniciados (el numerador va acá, el denominador allá)",
    ),
    "pacientes_dados_alta": MetricaInfo(
        "Pacientes dados de alta",
        "Cantidad de pacientes que terminaron su tratamiento y recibieron el alta en el período.",
        "conteo",
    ),
    "pacientes_vuelven_control": MetricaInfo(
        "Pacientes que vuelven a control",
        "De los pacientes dados de alta, cuántos vuelven a su control periódico en el plazo esperado.",
        "conteo",
        no_confundir_con="pacientes_reactivados (esos son pacientes INACTIVOS que se reactivan, no pacientes en control regular)",
    ),
    "pacientes_inactivos_contactados": MetricaInfo(
        "Pacientes inactivos contactados",
        "Cantidad de pacientes que llevan tiempo sin venir (inactivos) a los que la clínica contactó para reactivarlos en el período.",
        "conteo",
    ),
    "pacientes_reactivados": MetricaInfo(
        "Pacientes reactivados",
        "De esos pacientes inactivos contactados, cuántos efectivamente volvieron.",
        "conteo",
        no_confundir_con="pacientes_vuelven_control (retención normal, no reactivación de inactivos)",
    ),
    "pacientes_atendidos_periodo": MetricaInfo(
        "Pacientes atendidos en el período",
        "Cantidad total de pacientes distintos atendidos (cualquier motivo) en el período — la base sobre la que se miden reseñas/referidos.",
        "conteo",
        no_confundir_con="consultas_nuevas_mes (esos son solo los NUEVOS, este es todo paciente atendido)",
    ),
    "resenas_nuevas": MetricaInfo(
        "Reseñas nuevas",
        "Cantidad de reseñas nuevas (Google, redes) recibidas en el período.",
        "conteo",
    ),
    "referidos_nuevos": MetricaInfo(
        "Referidos nuevos",
        "Cantidad de pacientes nuevos que llegaron por referido de otro paciente en el período.",
        "conteo",
        no_confundir_con="canal_captacion == 'Referido' en un CSV transaccional es la misma idea, contar esas filas",
    ),
    "monto_cobrado": MetricaInfo(
        "Monto cobrado",
        "Suma en ARS de lo EFECTIVAMENTE cobrado en el período (dinero que entró).",
        "monto_ars",
        no_confundir_con="monto_facturado (lo facturado puede no estar cobrado todavía) ni monto_presupuestos_aceptados",
    ),
    "monto_facturado": MetricaInfo(
        "Monto facturado",
        "Suma en ARS de lo facturado en el período, cobrado o no todavía. monto_cobrado <= monto_facturado siempre.",
        "monto_ars",
    ),
    "gasto_captacion": MetricaInfo(
        "Gasto en captación",
        "Gasto en ARS en marketing/publicidad para captar pacientes nuevos en el período.",
        "monto_ars",
        no_confundir_con="gasto_reactivacion (ese es gasto en recuperar pacientes inactivos, no en captar nuevos)",
    ),
    "pacientes_nuevos_captados": MetricaInfo(
        "Pacientes nuevos captados",
        "Cantidad de pacientes nuevos que se sumaron en el período (denominador del costo de adquisición).",
        "conteo",
    ),
    "gasto_reactivacion": MetricaInfo(
        "Gasto en reactivación",
        "Gasto en ARS en recuperar pacientes inactivos en el período.",
        "monto_ars",
        no_confundir_con="gasto_captacion (ese es para pacientes nuevos, no inactivos)",
    ),
    "ingreso_por_paciente": MetricaInfo(
        "Ingreso por paciente",
        "Desglose {paciente: monto histórico total} — cuánto generó cada paciente a lo largo del tiempo, no en un solo período.",
        "monto_ars",
    ),
    "ingreso_por_tratamiento": MetricaInfo(
        "Ingreso por tipo de tratamiento",
        "Desglose {tipo_de_tratamiento: ingreso total}. En un CSV transaccional, agrupar el monto por la columna de tratamiento.",
        "monto_ars",
        no_confundir_con="costo_por_tratamiento (eso es lo que CUESTA el insumo, no lo que ingresa)",
    ),
    "costo_por_tratamiento": MetricaInfo(
        "Costo por tipo de tratamiento",
        "Desglose {tipo_de_tratamiento: costo de insumos}. Es un COSTO, no un ingreso.",
        "monto_ars",
        no_confundir_con="ingreso_por_tratamiento (eso es lo que se cobra, no lo que cuesta)",
    ),
    "costo_hora_sillon": MetricaInfo(
        "Costo por hora-sillón",
        "Costo operativo en ARS de una hora de sillón ocupado (alquiler, personal, etc. prorrateado).",
        "monto_ars",
    ),
    "duracion_tratamiento_horas": MetricaInfo(
        "Duración por tipo de tratamiento",
        "Desglose {tipo_de_tratamiento: horas que ocupa en el sillón}.",
        "horas",
    ),
    "horas_sillon_ocupadas": MetricaInfo(
        "Horas-sillón ocupadas",
        "Total de horas de sillón efectivamente ocupadas (con paciente) en el período.",
        "horas",
    ),
    "tiempo_respuesta_promedio_min": MetricaInfo(
        "Tiempo de 1ª respuesta",
        "Cuánto tarda LA CLÍNICA en responder a una consulta/lead NUEVO "
        "(primer contacto — WhatsApp, teléfono, etc.), en MINUTOS.",
        "minutos",
        no_confundir_con=(
            "cuánto tarda un PACIENTE en aceptar/rechazar un presupuesto ya "
            "enviado — eso es otro dato (dias_hasta_respuesta de un "
            "presupuesto), no esta variable. Si la fuente da el dato en "
            "horas o días, hay que convertirlo a minutos."
        ),
    ),
    "horas_tarea_manual_semana": MetricaInfo(
        "Horas/semana en tareas manuales repetitivas",
        "Desglose {tarea: horas/semana que insume}, o si la fuente solo da "
        "un total ya agregado sin desglose por tarea, un total único. "
        "SIEMPRE en HORAS, nunca en minutos ni en porcentaje.",
        "horas",
        no_confundir_con=(
            "tareas_sin_backup (esa es una LISTA de tareas críticas, no "
            "horas) ni automatizaciones_activas (esa es interna, nunca "
            "viene de un archivo) ni ningún % de automatización"
        ),
    ),
    "tareas_sin_backup": MetricaInfo(
        "Tareas sin backup",
        "Lista de tareas críticas que dependen de una sola persona — cada "
        "elemento debería poder identificar la tarea (y quién la hace, si "
        "está disponible). Si la fuente solo da un CONTEO suelto (ej. '4 "
        "tareas críticas') sin nombrarlas, no hay lista real: mejor no "
        "mapear la variable que inventar nombres de tarea.",
        "lista_de_tareas",
        no_confundir_con="horas_tarea_manual_semana (esa es horas, no una lista de qué tareas)",
    ),
}

# Variables internas no llevan MetricaInfo — nunca deberían llegar a un
# prompt de extracción (ver INTERNAL_VARIABLES arriba y validacion.py).

METRICAS_EXTRAIBLES: dict[str, MetricaInfo] = {
    v: info for v, info in METRICAS.items() if v not in INTERNAL_VARIABLES
}


@dataclass
class KPIFormula:
    id: int
    nombre: str
    variables: list[str]
    calcular: Callable[[dict], Optional[float]]
    unidad: str = "%"
    nota: str = ""
    # Estructura declarada de la fórmula, SOLO para los KPIs porcentuales
    # cuya forma es exactamente _pct(numerador, denominador) con una
    # variable de cada lado. `calcular` es un lambda opaco: no hay forma de
    # saber en runtime cuál variable es el numerador y cuál el denominador,
    # y adivinarlo es justamente el tipo de atajo que produjo el bug de
    # confundir la columna de tasa con la de conteo. Declararlo a mano acá
    # es lo que habilita a derivacion.py a completar una variable faltante
    # a partir de la tasa que la planilla ya trae calculada, sin inferir
    # nada. Si un KPI no los declara, la derivación simplemente no se
    # dispara para él — el default seguro.
    numerador: Optional[str] = None
    denominador: Optional[str] = None


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
               lambda v: _pct(v["turnos_agendados"], v["consultas_nuevas_mes"]),
               numerador="turnos_agendados", denominador="consultas_nuevas_mes"),

    KPIFormula(4, "Tasa de no-show",
               ["no_shows", "turnos_agendados"],
               lambda v: _pct(v["no_shows"], v["turnos_agendados"]),
               numerador="no_shows", denominador="turnos_agendados"),

    KPIFormula(5, "Tasa de aceptación de presupuestos",
               ["presupuestos_aceptados", "presupuestos_emitidos"],
               lambda v: _pct(v["presupuestos_aceptados"], v["presupuestos_emitidos"]),
               numerador="presupuestos_aceptados", denominador="presupuestos_emitidos"),

    KPIFormula(6, "Ticket promedio",
               ["monto_presupuestos_aceptados", "presupuestos_aceptados"],
               lambda v: round(v["monto_presupuestos_aceptados"] / v["presupuestos_aceptados"], 2)
               if v["presupuestos_aceptados"] else None,
               unidad="$"),

    KPIFormula(7, "Tasa de finalización de tratamiento",
               ["tratamientos_completados", "tratamientos_iniciados"],
               lambda v: _pct(v["tratamientos_completados"], v["tratamientos_iniciados"]),
               numerador="tratamientos_completados", denominador="tratamientos_iniciados"),

    KPIFormula(8, "Recall / retención",
               ["pacientes_vuelven_control", "pacientes_dados_alta"],
               lambda v: _pct(v["pacientes_vuelven_control"], v["pacientes_dados_alta"]),
               numerador="pacientes_vuelven_control", denominador="pacientes_dados_alta"),

    KPIFormula(9, "Tasa de reactivación",
               ["pacientes_reactivados", "pacientes_inactivos_contactados"],
               lambda v: _pct(v["pacientes_reactivados"], v["pacientes_inactivos_contactados"]),
               numerador="pacientes_reactivados", denominador="pacientes_inactivos_contactados"),

    # KPI 10 NO declara numerador/denominador a propósito: su numerador es
    # una suma de dos variables (resenas + referidos), así que conocer la
    # tasa no determina un valor único para ninguna de las dos. Sin los
    # campos, derivacion.py nunca se dispara acá.
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
               lambda v: _pct(v["monto_cobrado"], v["monto_facturado"]),
               numerador="monto_cobrado", denominador="monto_facturado"),

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
