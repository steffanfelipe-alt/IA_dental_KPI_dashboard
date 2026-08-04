"""
preguntas_wizard.py

Las preguntas de "Preguntas_Diagnostico_Odontologia.docx" están escritas
para una LLAMADA de venta: conversacionales, y varias piden una proporción
("de cada 10 turnos, ¿cuántos son no-show?") en vez de un número crudo.
Eso funciona bien al teléfono, pero el wizard de la app necesita datos
numéricos separados para poder calcular las fórmulas de schema.py.

Este archivo es el puente: por cada variable no-interna y no-financiera,
define el texto exacto que ve el dueño en el wizard, más la referencia a
la pregunta original de la guía para trazabilidad.

Cuando "adaptada=True", la pregunta de acá pide un dato crudo que en la
guía aparecía como proporción o como pregunta cualitativa — son cosas
distintas aunque compartan número de referencia.
"""

from dataclasses import dataclass


@dataclass
class PreguntaWizard:
    variable: str
    pregunta: str
    tipo_input: str          # "number" | "decimal" | "list" | "dict_horas"
    referencia_guia: str      # P# de Preguntas_Diagnostico_Odontologia_v2.docx
    adaptada: bool = False    # True si en la guía era proporción/cualitativa, no un número crudo


PREGUNTAS_WIZARD: dict[str, PreguntaWizard] = {

    "consultas_nuevas_mes": PreguntaWizard(
        "consultas_nuevas_mes",
        "En un mes normal, ¿cuántas consultas nuevas reciben en total (WhatsApp, redes, teléfono)?",
        "number", "P9b"),

    "turnos_agendados": PreguntaWizard(
        "turnos_agendados",
        "¿Cuántos turnos agendan por semana, aproximadamente?",
        "number", "P3", adaptada=True),

    "turnos_asistidos": PreguntaWizard(
        "turnos_asistidos",
        "De esos turnos agendados, ¿a cuántos asistió el paciente?",
        "number", "P3", adaptada=True),

    "no_shows": PreguntaWizard(
        "no_shows",
        "De esos, ¿cuántos terminan siendo no-show o cancelación de último momento?",
        "number", "P3", adaptada=True),

    "turnos_cancelados": PreguntaWizard(
        "turnos_cancelados",
        "Y de esos que faltan, ¿cuántos avisan que cancelan (a diferencia de los que "
        "simplemente no aparecen)?",
        "number", "P3", adaptada=True),

    "presupuestos_emitidos": PreguntaWizard(
        "presupuestos_emitidos",
        "¿Cuántos presupuestos arman por mes, aproximadamente?",
        "number", "P21", adaptada=True),

    "presupuestos_aceptados": PreguntaWizard(
        "presupuestos_aceptados",
        "De esos presupuestos, ¿cuántos terminan aceptados?",
        "number", "P21", adaptada=True),

    "monto_presupuestos_aceptados": PreguntaWizard(
        "monto_presupuestos_aceptados",
        "¿Cuál es el ticket promedio de un tratamiento, o el rango de precio de los más comunes?",
        "decimal", "P21b"),

    "monto_presupuestos_emitidos": PreguntaWizard(
        "monto_presupuestos_emitidos",
        "¿Cuál es, aproximadamente, el monto total en pesos de todos los presupuestos "
        "que armaron por mes (aceptados o no)?",
        "decimal", "P21b", adaptada=True),

    "tratamientos_iniciados": PreguntaWizard(
        "tratamientos_iniciados",
        "¿Cuántos tratamientos de varias sesiones arrancan por mes, aproximadamente?",
        "number", "P22", adaptada=True),

    "tratamientos_completados": PreguntaWizard(
        "tratamientos_completados",
        "De esos, ¿cuántos terminan completándose todas las sesiones?",
        "number", "P22", adaptada=True),

    "pacientes_dados_alta": PreguntaWizard(
        "pacientes_dados_alta",
        "¿Cuántos pacientes dan de alta (terminan tratamiento) por mes, aproximadamente?",
        "number", "P40", adaptada=True),

    "pacientes_vuelven_control": PreguntaWizard(
        "pacientes_vuelven_control",
        "De esos, ¿cuántos vuelven a su control en el plazo esperado?",
        "number", "P42", adaptada=True),

    "pacientes_inactivos_contactados": PreguntaWizard(
        "pacientes_inactivos_contactados",
        "¿A cuántos pacientes inactivos contactan por mes para intentar reactivarlos?",
        "number", "P43", adaptada=True),

    "pacientes_reactivados": PreguntaWizard(
        "pacientes_reactivados",
        "De esos, ¿cuántos efectivamente vuelven?",
        "number", "P43", adaptada=True),

    "pacientes_inactivos_total": PreguntaWizard(
        "pacientes_inactivos_total",
        "¿Cuántos pacientes tenés hoy inactivos en total — que hace más de un año que no vienen?",
        "number", "P43", adaptada=True),

    "pacientes_activos_cartera": PreguntaWizard(
        "pacientes_activos_cartera",
        "¿Cuántos pacientes tenés hoy activos en total — que vinieron en el último año?",
        "number", "P43", adaptada=True),

    "pacientes_atendidos_periodo": PreguntaWizard(
        "pacientes_atendidos_periodo",
        "¿Cuántos pacientes atienden en total por mes?",
        "number", "P41", adaptada=True),

    "resenas_nuevas": PreguntaWizard(
        "resenas_nuevas",
        "¿Cuántas reseñas nuevas reciben por mes, aproximadamente?",
        "number", "P41", adaptada=True),

    "referidos_nuevos": PreguntaWizard(
        "referidos_nuevos",
        "¿Cuántos pacientes nuevos llegan por referido de otro paciente al mes?",
        "number", "P41", adaptada=True),

    "pacientes_nuevos_captados": PreguntaWizard(
        "pacientes_nuevos_captados",
        "¿Cuántos pacientes nuevos captan por mes en total?",
        "number", "P36", adaptada=True),

    "tiempo_respuesta_promedio_min": PreguntaWizard(
        "tiempo_respuesta_promedio_min",
        "Cuando alguien consulta por primera vez, ¿cuánto tardan en responder, en minutos u horas?",
        "number", "P37"),

    "horas_tarea_manual_semana": PreguntaWizard(
        "horas_tarea_manual_semana",
        "¿Cuántas horas por semana dedican, a mano, a: gestionar la agenda / responder WhatsApp "
        "y consultas repetidas / facturación y cobros? (una respuesta por tarea)",
        "dict_horas", "P8, P28", adaptada=True),

    "tareas_sin_backup": PreguntaWizard(
        "tareas_sin_backup",
        "¿Hay tareas que dependen exclusivamente de una sola persona y nadie más sabe hacer? ¿Cuáles, y quién las hace?",
        "list", "P33, P34"),
}


def obtener_pregunta(variable: str) -> PreguntaWizard | None:
    return PREGUNTAS_WIZARD.get(variable)
