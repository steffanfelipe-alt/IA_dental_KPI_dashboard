"""
guia_diagnostico.py

Catálogo de las 55 preguntas de Preguntas_Diagnostico_Odontologia_v2.docx
(53 originales + P9b + P21b), con el flag `requerida_diagnostico` que
distingue las que el onboarding web tiene que pedir de las que quedan
registradas en el catálogo pero sin valor en `respuestas_diagnostico`.

Cómo se decide `requerida_diagnostico` (para cada pregunta, `True` si CUALQUIERA se cumple):
  1. Es NÚCLEO (bloques 1, 2, 4 y 10 del docx — el mínimo que el propio
     documento define para calificar al cliente en una llamada corta).
  2. Está referenciada de verdad por el pipeline aunque el docx la marque
     ⚪ Contexto: contexto_cualitativo.py (CONTEXTO_CUALITATIVO_POR_KPI +
     CONTEXTO_GENERAL), diagnostico.py (P2, P51), estacionalidad.py (P51)
     o catalogo_tecnologico.py (P45) — P2/P45/P51 ya caen en (1) o en
     CONTEXTO_GENERAL, así que no hace falta listarlos aparte.

Quedan en `False` sólo 7: P15-P18 (historia clínica/consentimientos en
papel, bloque 3), P31 (frecuencia de pedidos a proveedores), P35
(capacitación de personal nuevo) y P39 (conversión de consulta a primer
turno) — hoy ningún módulo las lee. Siguen en el catálogo por si una
auditoría más profunda las necesita más adelante, pero el onboarding web
no las pregunta.

Decisión tomada con Felipe el 2026-08-06: reemplaza la idea inicial de
"onboarding = solo Núcleo" — ese recorte apagaba en silencio el contexto
cualitativo completo de 6 KPIs (8, 9, 10, 12, 13, 19) y la estacionalidad
(P51) que `estacionalidad.py` chequea directo.
"""

from dataclasses import dataclass


@dataclass
class PreguntaGuia:
    id: str
    texto: str
    bloque: int
    nombre_bloque: str
    nucleo: bool                  # True si el docx la marca 🔶 NÚCLEO
    requerida_diagnostico: bool   # True si el onboarding web tiene que pedirla


# (nombre del bloque, si el docx lo marca 🔶 NÚCLEO)
_BLOQUES: dict[int, tuple[str, bool]] = {
    1: ("Recepción, agenda y gestión de turnos", True),
    2: ("Comunicación con pacientes (antes, durante y después)", True),
    3: ("Historia clínica, documentación y consentimientos", False),
    4: ("Presupuestos, ventas y conversión de tratamientos", True),
    5: ("Cobros, facturación y finanzas", False),
    6: ("Insumos, stock y proveedores", False),
    7: ("Personal, equipo y capacitación", False),
    8: ("Marketing y captación de nuevos pacientes", False),
    9: ("Experiencia y retención de pacientes", False),
    10: ("Tecnología y sistemas actuales", True),
    11: ("Gestión, reportes y toma de decisiones", False),
    12: ("Cumplimiento y regulaciones", False),
}

# Preguntas de bloques ⚪ Contexto que sí están referenciadas por el
# pipeline (ver docstring del módulo) — el onboarding web las pregunta
# igual, aunque el docx no las marque NÚCLEO.
_CONTEXTO_REQUERIDO = {
    "P24", "P25", "P26", "P27", "P28",
    "P29", "P30",
    "P32", "P33", "P34",
    "P36", "P37", "P38",
    "P40", "P41", "P42", "P43",
    "P48", "P49", "P50", "P51",
    "P52", "P53",
}


def _pregunta(id_: str, texto: str, bloque: int) -> PreguntaGuia:
    nombre_bloque, nucleo = _BLOQUES[bloque]
    requerida = nucleo or id_ in _CONTEXTO_REQUERIDO
    return PreguntaGuia(id_, texto, bloque, nombre_bloque, nucleo, requerida)


GUIA_DIAGNOSTICO: dict[str, PreguntaGuia] = {
    p.id: p for p in [
        # Bloque 1 — Recepción, agenda y gestión de turnos (NÚCLEO)
        _pregunta("P1", "¿Cómo se agenda hoy un turno — a mano, en un sistema, mezcla de los dos?", 1),
        _pregunta("P2", "¿Cómo confirman los turnos antes de la cita? ¿Quién lo hace y con qué frecuencia?", 1),
        _pregunta("P3", "De cada 10 turnos agendados, ¿cuántos terminan siendo no-show o cancelación de último momento?", 1),
        _pregunta("P4", "¿Cuánto vale en promedio el turno o tratamiento que se pierde cuando un paciente falta?", 1),
        _pregunta("P5", "Cuando un paciente falta sin avisar, ¿qué pasa con ese hueco — se reemplaza o queda vacío?", 1),
        _pregunta("P6", "¿Tienen lista de espera para turnos que se cancelan? ¿Cómo la manejan?", 1),
        _pregunta("P7", "¿Pasa que se pisan turnos o se agenda dos veces el mismo horario?", 1),
        _pregunta("P8", "¿Cuánto tiempo del día dedica el equipo de recepción solo a gestionar la agenda?", 1),

        # Bloque 2 — Comunicación con pacientes (NÚCLEO)
        _pregunta("P9", "¿Cuáles son las preguntas que más se repiten por WhatsApp, teléfono o mail — las que responden casi todos los días?", 2),
        _pregunta("P9b", "En un mes normal, ¿cuántas consultas nuevas reciben en total, contando todos los canales — WhatsApp, redes, teléfono?", 2),
        _pregunta("P10", "¿Explican instrucciones de preparación antes de un tratamiento? ¿Cómo se lo comunican al paciente?", 2),
        _pregunta("P11", "¿Y después del tratamiento — hacen seguimiento de cuidados post-operatorios? ¿De qué forma?", 2),
        _pregunta("P12", "¿Alguna vez un paciente se complicó por no haber entendido bien una indicación pre o post tratamiento?", 2),
        _pregunta("P13", "¿Cuántos canales de contacto manejan en paralelo — WhatsApp, Instagram, teléfono, mail? ¿Se mezclan o hay uno principal?", 2),
        _pregunta("P14", "¿Quién responde los mensajes fuera de horario de atención, si es que alguien lo hace?", 2),

        # Bloque 3 — Historia clínica, documentación y consentimientos (Contexto, sin consumidor en código)
        _pregunta("P15", "¿La historia clínica de cada paciente está digitalizada o en papel?", 3),
        _pregunta("P16", "¿Los consentimientos informados se firman en papel o ya tienen algo digital?", 3),
        _pregunta("P17", "¿Cómo hacen para no perder documentación de un paciente si pasa por varios profesionales de la clínica?", 3),
        _pregunta("P18", "¿Tuvieron alguna vez un problema por no encontrar o no tener firmado algún documento a tiempo?", 3),

        # Bloque 4 — Presupuestos, ventas y conversión de tratamientos (NÚCLEO)
        _pregunta("P19", "¿Cómo se arma un presupuesto hoy — quién lo hace y en qué formato se lo dan al paciente?", 4),
        _pregunta("P20", "Cuando le dan un presupuesto a alguien y no responde enseguida, ¿hacen algún seguimiento después?", 4),
        _pregunta("P21", "De los presupuestos que arman en un mes, ¿tenés una idea de cuántos terminan aceptados?", 4),
        _pregunta("P21b", "¿Cuál es el ticket promedio de un tratamiento, o el rango de precio de los tratamientos más comunes?", 4),
        _pregunta("P22", "¿Qué pasa con un tratamiento de varias sesiones si el paciente empieza y después deja de venir?", 4),
        _pregunta("P23", "¿Alguna vez perdieron un paciente por tardar en responder con el presupuesto o la información que pedía?", 4),

        # Bloque 5 — Cobros, facturación y finanzas (Contexto, requerida por código)
        _pregunta("P24", "¿Cómo cobran hoy — efectivo, transferencia, tarjeta, financiación propia?", 5),
        _pregunta("P25", "Si ofrecen financiación en cuotas, ¿quién explica las condiciones al paciente? ¿Es siempre la misma explicación?", 5),
        _pregunta("P26", "¿Tienen pacientes con pagos atrasados? ¿Cómo hacen el seguimiento de esos cobros?", 5),
        _pregunta("P27", "¿La facturación está integrada con la agenda y la historia clínica, o son sistemas separados?", 5),
        _pregunta("P28", "¿Cuánto tiempo por semana dedican a temas de facturación y cobros administrativos?", 5),

        # Bloque 6 — Insumos, stock y proveedores (Contexto; P31 sin consumidor)
        _pregunta("P29", "¿Cómo controlan el stock de insumos — hay un sistema o se controla a ojo?", 6),
        _pregunta("P30", "¿Alguna vez tuvieron que reprogramar un turno por falta de algún insumo o material?", 6),
        _pregunta("P31", "¿Quién se encarga de pedir a los proveedores y con qué frecuencia?", 6),

        # Bloque 7 — Personal, equipo y capacitación (Contexto; P35 sin consumidor)
        _pregunta("P32", "¿Cuántas personas trabajan en la clínica hoy, entre profesionales y administrativos?", 7),
        _pregunta("P33", "Si la persona de recepción falta un día, ¿qué pasa con la agenda y la comunicación con pacientes?", 7),
        _pregunta("P34", "¿Hay tareas que dependen exclusivamente de una sola persona y nadie más sabe hacer?", 7),
        _pregunta("P35", "¿Cómo capacitan a alguien nuevo que se suma al equipo — hay un proceso o se aprende sobre la marcha?", 7),

        # Bloque 8 — Marketing y captación de nuevos pacientes (Contexto; P39 sin consumidor)
        _pregunta("P36", "¿De dónde vienen hoy la mayoría de los pacientes nuevos — redes, recomendación, Google, otro?", 8),
        _pregunta("P37", "Cuando alguien consulta por redes o WhatsApp por primera vez, ¿cuánto tardan en responderle?", 8),
        _pregunta("P38", "¿Hacen algún tipo de campaña o promoción estacional (blanqueamiento, ortodoncia, estética)?", 8),
        _pregunta("P39", "¿Miden cuántas consultas nuevas se convierten en primer turno agendado?", 8),

        # Bloque 9 — Experiencia y retención de pacientes (Contexto, requerida por código)
        _pregunta("P40", "Después de un tratamiento, ¿hacen algún seguimiento para saber cómo quedó el paciente?", 9),
        _pregunta("P41", "¿Piden reseñas o testimonios después de una atención? ¿De qué forma?", 9),
        _pregunta("P42", "¿Tienen algún sistema para recordarle a un paciente que ya pasó mucho tiempo desde su último control?", 9),
        _pregunta("P43", "¿Cómo describirías la relación con los pacientes que dejan de venir — se pierden del todo o vuelven solos?", 9),

        # Bloque 10 — Tecnología y sistemas actuales (NÚCLEO)
        _pregunta("P44", "¿Qué sistema usan para la agenda? ¿Y para la historia clínica?", 10),
        _pregunta("P45", "¿Esos sistemas están conectados entre sí, o cada uno funciona por separado?", 10),
        _pregunta("P46", "¿Alguna vez probaron algo automático — recordatorios por SMS, un bot, turnos online? ¿Cómo les fue?", 10),
        _pregunta("P47", "¿Quién en el equipo se siente más cómodo con la tecnología, y quién menos?", 10),

        # Bloque 11 — Gestión, reportes y toma de decisiones (Contexto, requerida por código)
        _pregunta("P48", "¿Quién más, además de vos, estaría involucrado en decidir algo como esto?", 11),
        _pregunta("P49", "¿Revisás algún número o reporte de la clínica de forma regular — turnos, facturación, no-shows?", 11),
        _pregunta("P50", "¿Hay algo que te gustaría medir hoy y no podés porque no tenés cómo?", 11),
        _pregunta("P51", "¿Hay alguna época del año donde todo esto se complica más — antes del verano, alguna campaña, algún pico de turnos?", 11),

        # Bloque 12 — Cumplimiento y regulaciones (Contexto, requerida por código)
        _pregunta("P52", "¿Hay algún requisito legal o de colegio profesional sobre cómo se comunican con los pacientes que debamos tener en cuenta?", 12),
        _pregunta("P53", "¿Manejan datos sensibles de pacientes que tengan alguna restricción particular de privacidad?", 12),
    ]
}

PREGUNTAS_REQUERIDAS_ONBOARDING: dict[str, PreguntaGuia] = {
    id_: p for id_, p in GUIA_DIAGNOSTICO.items() if p.requerida_diagnostico
}
