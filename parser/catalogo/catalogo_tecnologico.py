"""
catalogo_tecnologico.py

Fase 5 del plan de evolución: mapea cada diagnóstico (diagnostico.py) a
una intervención concreta del catálogo real de servicios de Agencia IA —
nunca deja que Claude invente una solución desde cero (§13 del Documento
Maestro). Indexado por ETAPA del funnel (Captación → Conversión →
Confirmación → Consulta → Post-consulta → Fidelización → Referidos), que
es la forma en la que llegó el catálogo y que encastra mejor que una
tabla plana: `diagnosticar()` ya dice en qué KPI está el cuello, y la
etapa correspondiente da las intervenciones candidatas sin traducción.

## Los 3 campos que el catálogo no traía

1. **`tipo`** (proceso | automatizacion | ia): el §14 exige poder
   recomendar un cambio de protocolo en vez de tecnología. El catálogo
   ya incluye 9 alternativas de proceso (🅿️), repartidas en las 4 etapas
   que antes no tenían ninguna (captación, conversión, consulta,
   post_consulta), cada una con su propia debilidad documentada en
   `durabilidad` — condición cero, pero depende de que un humano no
   falle.
2. **`periodo_evaluacion_semanas`**: NO se completa acá — es el único
   campo que sigue pendiente del usuario (cuántas semanas antes de medir
   si una intervención movió el KPI). Queda en `None` hasta confirmarlo.
3. **`kpi_objetivo` / `variable_objetivo` / `metrica_paciente`**: derivado
   del cruce contra schema.py — ver la nota de "4 métricas sin KPI" más
   abajo.

## Hallazgo: 4 métricas objetivo del catálogo no tenían KPI que las mida

Cruzando las métricas objetivo del catálogo contra los 16 KPIs de
schema.py, "hora-sillón ociosa", "tiempo de respuesta a urgencias" y
"tiempo de respuesta a reclamos" no tenían variable propia — se agregaron
en la Fase 1 (`horas_sillon_disponibles`, `tiempo_respuesta_urgencias_min`,
`tiempo_respuesta_reclamos_min`). "Reputación" (pedido de reseña) sigue
sin mapear 1:1 — el catálogo mismo lo marca así; se aproxima con KPI 10
(reseñas/referidos) hasta que se decida si necesita variable propia.

## Por qué varias intervenciones dependen de metricas_paciente.py

"Predictor de riesgo de no-show", "reactivación de inactivos 8+ meses",
"programa de referidos con tracking", "campañas estacionales segmentadas"
y "recordatorio de controles según último control" no se pueden recomendar
con fundamento sin identidad de paciente — son exactamente las 5 que la
Fase 2 predijo que dependerían de `metricas_paciente.py` (ver `metrica_paciente`
de cada una más abajo).
"""

from dataclasses import dataclass
from typing import Optional

from parser.diagnostico.diagnostico import Diagnostico, EstadoEvidencia


# Fase H2: cuántas semanas esperar antes de medir si una intervención movió
# el KPI, por tipo. Un cambio de protocolo (proceso) se nota rápido porque
# no depende de que nadie construya nada; una automatización necesita
# acumular varias corridas para que el efecto se distinga del ruido; un
# modelo de IA necesita todavía más historia para que su señal sea
# legible (y muchas veces empieza más débil mientras "aprende" el
# contexto de la clínica).
SEMANAS_EVALUACION_POR_TIPO: dict[str, int] = {"proceso": 4, "automatizacion": 8, "ia": 12}


@dataclass
class Intervencion:
    id: str
    etapa: str
    nombre: str
    tipo: str  # "proceso" | "automatizacion" | "ia"
    metrica_objetivo: str
    kpi_objetivo: Optional[int] = None
    metrica_paciente: Optional[str] = None    # nombre de función de metricas_paciente.py, si aplica
    variable_objetivo: Optional[str] = None   # variable de schema.py, cuando no hay KPI mapeable
    condicion: str = "Ninguna"
    requiere_compliance: Optional[str] = None
    # Fase H2: None (default) se completa solo en __post_init__ según
    # `tipo` — mismo patrón que VariableValue.metodo en coverage.py (Fase
    # D1): ninguna de las 35 declaraciones de abajo necesitó cambiar. Se
    # puede pasar explícito si algún caso puntual necesita otro valor.
    periodo_evaluacion_semanas: Optional[int] = None
    durabilidad: Optional[str] = None  # solo alternativas de proceso: su debilidad conocida
    # Fase I3: antes esto se inferí­a de `condicion` con un keyword-match
    # ("api"/"integrad"/"conectad"/"sistema") — un artefacto de REDACCIÓN,
    # no de mérito: "Acceso a API de mensajería" quedaba penalizado y
    # "Necesita tracking/webhook en la landing" (también una integración
    # real) zafaba porque no contenía ninguna de esas palabras. Ahora es
    # una decisión explícita por intervención; None cae al keyword-match
    # de siempre (retrocompatible, no rompe nada que no se declare acá).
    requiere_integracion: Optional[bool] = None
    # Fase I3: una intervención puede mover más de un KPI (ej. un agente
    # de agendamiento 24/7 no sólo sube la conversión — también baja el
    # tiempo de primera respuesta). kpi_objetivo sigue siendo EL KPI que
    # mejor la define; kpis_secundarios son los que también matchea
    # mapear_oportunidades, sin ser el foco principal.
    kpis_secundarios: tuple = ()
    # Fase I4: antes no existía ningún campo de texto que explicara la
    # intervención — la sección 7 sólo podía mostrar nombre/tipo/etapa/
    # condición. Sin esto, no hay forma de decirle al dueño de la clínica
    # POR QUÉ le conviene ni QUÉ hace concretamente.
    como_funciona: str = ""
    beneficio: str = ""

    def __post_init__(self):
        if self.periodo_evaluacion_semanas is None:
            self.periodo_evaluacion_semanas = SEMANAS_EVALUACION_POR_TIPO.get(self.tipo)


ETAPAS = [
    "captacion", "conversion", "confirmacion", "consulta",
    "post_consulta", "fidelizacion", "referidos",
]

INTERVENCIONES: list[Intervencion] = [
    # 1. Captación / Atracción
    Intervencion(
        "chatbot_captacion_redes", "captacion", "Chatbot de captación en redes", "ia",
        "Tiempo de primera respuesta", kpi_objetivo=2,
        condicion="Acceso a API de mensajería de Instagram/Meta Business",
        requiere_integracion=True,
        como_funciona="Responde automáticamente el primer mensaje de un lead en Instagram/WhatsApp, apenas llega, sin esperar a que alguien del equipo lo vea.",
        beneficio="El tiempo de primera respuesta pasa de horas a segundos — es la intervención directa para este KPI cuando el problema es que la clínica tarda en contestar.",
    ),
    Intervencion(
        "calificador_leads_reglas", "captacion", "Calificador automático de leads (reglas fijas)", "automatizacion",
        "Tasa de conversión lead→turno", kpi_objetivo=3,
        condicion="Ninguna especial (corre sobre WhatsApp)",
        requiere_integracion=False,
        como_funciona="Hace unas preguntas fijas por WhatsApp (motivo de consulta, obra social, urgencia) antes de pasar el lead a un humano.",
        beneficio="Menos tiempo perdido con leads que no calificaban, y el equipo llega a la conversación ya con contexto.",
    ),
    Intervencion(
        "calificador_leads_ia", "captacion", "Calificador automático de leads (interpreta texto libre)", "ia",
        "Tasa de conversión lead→turno", kpi_objetivo=3,
        condicion="Ninguna especial (corre sobre WhatsApp)",
        requiere_integracion=False,
        como_funciona="Igual que el calificador de reglas fijas, pero entiende lo que el lead escribe con sus propias palabras en vez de exigir respuestas de menú.",
        beneficio="Capta leads que no seguirían un flujo de opciones rígido — más cobertura que la versión de reglas fijas.",
    ),
    Intervencion(
        "retargeting_formularios", "captacion", "Retargeting de formularios abandonados", "automatizacion",
        "Tasa de conversión lead→turno", kpi_objetivo=3,
        condicion="Necesita tracking/webhook en la landing",
        requiere_integracion=True,
        como_funciona="Detecta cuando alguien empezó a llenar el formulario de la web y no lo terminó, y le manda un mensaje de seguimiento.",
        beneficio="Recupera leads que ya mostraron interés y se perdieron en el camino — no es un problema de primer contacto, es de conversión.",
    ),
    Intervencion(
        "meta_ads_captacion", "captacion", "Meta Ads (Instagram/Facebook)", "ia",
        "Costo de adquisición vs. reactivación", kpi_objetivo=19,
        kpis_secundarios=(1,),
        condicion="Acceso a Meta Business Manager + cuenta publicitaria con historial",
        requiere_integracion=True,
        como_funciona="Corre campañas pagas en Instagram/Facebook con segmentación y creatividades optimizadas automáticamente (Advantage+) según qué público y qué aviso convierten mejor, en vez de un aviso fijo para todos.",
        beneficio="Baja el costo por lead nuevo porque el gasto se redirige solo hacia el público que efectivamente agenda, y de paso mete volumen adicional de consultas que hoy no llegan por ningún canal orgánico.",
    ),
    Intervencion(
        "google_ads_captacion", "captacion", "Google Ads (búsqueda)", "automatizacion",
        "Costo de adquisición vs. reactivación", kpi_objetivo=19,
        kpis_secundarios=(1,),
        condicion="Cuenta de Google Ads + presupuesto mensual asignado",
        requiere_integracion=True,
        como_funciona="Pone a la clínica arriba de los resultados de búsqueda para términos de alta intención (ej. \"implante dental cerca\"), con pujas ajustadas por conversión real y no solo por clic.",
        beneficio="Capta gente que ya está buscando activamente un tratamiento — el costo por consulta nueva es más controlable que en un canal de descubrimiento pasivo como redes.",
    ),
    Intervencion(
        "seo_organico_captacion", "captacion", "SEO (posicionamiento orgánico en Google)", "automatizacion",
        "Consultas nuevas / mes", kpi_objetivo=1,
        kpis_secundarios=(19,),
        condicion="Sitio web propio + acceso de administrador para optimizarlo",
        requiere_integracion=True,
        como_funciona="Optimiza la ficha técnica del sitio (velocidad, estructura, contenido por tratamiento) para que aparezca en los primeros resultados orgánicos de Google, sin pagar por clic.",
        beneficio="Suma consultas nuevas de forma sostenida sin costo por lead — a diferencia de un canal pago, el tráfico orgánico no se corta si baja el presupuesto de un mes al otro.",
    ),
    Intervencion(
        "referidos_organicos_gbp", "captacion", "Referidos orgánicos / Google Business Profile", "automatizacion",
        "Consultas nuevas / mes", kpi_objetivo=1,
        kpis_secundarios=(19,),
        condicion="Perfil de Google Business Profile reclamado y verificado",
        requiere_integracion=True,
        como_funciona="Optimiza y mantiene activo el perfil de Google Business (fotos, horarios, categorías, respuesta a reseñas) para que la clínica aparezca en el mapa y en las búsquedas locales con intención de agendar.",
        beneficio="El perfil de Google es lo primero que ve alguien que busca \"dentista cerca\" — mantenerlo completo y con reseñas activas convierte esa búsqueda local en consultas nuevas sin pagar por cada una.",
    ),
    Intervencion(
        "proceso_preguntar_como_nos_conocio", "captacion", "Preguntar \"¿cómo nos conociste?\" en cada primer contacto (sin sistema)", "proceso",
        "Consultas nuevas / mes (atribución por canal)", kpi_objetivo=1,
        kpis_secundarios=(19,),
        durabilidad="Depende de que quien atiende el primer contacto lo pregunte y lo anote siempre, sin excepción",
        requiere_integracion=False,
        como_funciona="Protocolo escrito: quien atiende el primer mensaje o llamada pregunta \"¿cómo nos encontraste?\" y anota la respuesta en una planilla simple, sin ninguna herramienta de tracking.",
        beneficio="Cuesta cero implementar y por primera vez da una idea de qué canal trae consultas nuevas — pero se cae apenas alguien se olvida de preguntar o de anotarlo.",
    ),

    # 2. Conversión / Agendamiento
    Intervencion(
        "agente_agendamiento_24_7", "conversion", "Agente de agendamiento 24/7", "ia",
        "Tasa de conversión a turno agendado", kpi_objetivo=3,
        kpis_secundarios=(2,),
        condicion="API contra la agenda real de la clínica (lo que preguntan P44/P45)",
        requiere_integracion=True,
        como_funciona="Conversa con el lead y agenda el turno directo contra la agenda real de la clínica, a cualquier hora, sin que nadie del equipo intervenga.",
        beneficio="Sube la conversión porque nadie espera hasta el horario de atención — y de paso baja el tiempo de primera respuesta a cero, porque responde al instante.",
    ),
    Intervencion(
        "seguimiento_leads_sin_confirmar", "conversion", "Seguimiento a leads sin confirmar", "automatizacion",
        "Tasa de conversión a turno agendado", kpi_objetivo=3,
        requiere_integracion=False,
        como_funciona="Si un lead recibió una propuesta de turno y no confirmó, le manda un recordatorio a las 24-48hs en vez de dejarlo morir.",
        beneficio="Recupera conversión que hoy se pierde en silencio — el lead ya fue contactado, sólo falta el empujón final.",
    ),
    Intervencion(
        "presupuesto_estimado_tabla", "conversion", "Presupuesto estimado automático (tabla fija)", "automatizacion",
        "Tasa de aceptación de presupuestos (indirecta)", kpi_objetivo=5,
        condicion="Lista de precios digitalizada",
        requiere_integracion=False,
        como_funciona="Devuelve un rango de precio automático según el tratamiento que pide el lead, usando una lista de precios fija.",
        beneficio="El lead sabe el costo aproximado antes de agendar, así que llega al turno menos propenso a rechazar el presupuesto por sorpresa.",
    ),
    Intervencion(
        "presupuesto_estimado_ia", "conversion", "Presupuesto estimado automático (personalizado)", "ia",
        "Tasa de aceptación de presupuestos (indirecta)", kpi_objetivo=5,
        condicion="Lista de precios digitalizada",
        requiere_integracion=False,
        como_funciona="Igual que la versión de tabla fija, pero ajusta el estimado según lo que el lead cuenta de su caso, no un rango genérico.",
        beneficio="Estimado más preciso que la tabla fija — menos sorpresa al momento del presupuesto real.",
    ),
    Intervencion(
        "recordatorio_documentacion_previa", "conversion", "Recordatorio de documentación previa", "automatizacion",
        "Horas repetitivas del equipo", kpi_objetivo=15,
        requiere_integracion=False,
        como_funciona="Manda automáticamente la lista de qué traer (estudios, DNI, orden médica) antes del turno.",
        beneficio="El equipo deja de repetir la misma explicación por teléfono turno tras turno.",
    ),
    Intervencion(
        "proceso_doble_confirmacion_manual", "conversion", "Doble confirmación manual del turno propuesto", "proceso",
        "Tasa de conversión a turno agendado", kpi_objetivo=3,
        durabilidad="Depende de que el mismo recepcionista repita la llamada de confirmación al día siguiente, sin saltarla por volumen de trabajo",
        requiere_integracion=False,
        como_funciona="Protocolo escrito: cuando se le propone un turno a un lead, recepción llama o escribe de nuevo al día siguiente para confirmar, en vez de darlo por perdido si no responde enseguida.",
        beneficio="Cuesta cero implementar y recupera algunos leads que dudaban — pero se pierde apenas el equipo está saturado o alguien nuevo no conoce el protocolo.",
    ),
    Intervencion(
        "proceso_guion_objeciones_presupuesto", "conversion", "Guion escrito para objeciones de presupuesto", "proceso",
        "Tasa de aceptación de presupuestos (indirecta)", kpi_objetivo=5,
        durabilidad="Depende de que quien presenta el presupuesto siga el guion en vez de responder de forma improvisada",
        requiere_integracion=False,
        como_funciona="Protocolo escrito con las objeciones de precio más comunes y la respuesta sugerida (financiación, urgencia del tratamiento, comparación con no tratarlo), para usar antes de que el lead cuelgue.",
        beneficio="Cuesta cero implementar y mejora la conversión de presupuestos dudosos — pero depende 100% de que cada persona del equipo lo use igual, sin criterio propio.",
    ),

    # 3. Confirmación y Pre-consulta
    Intervencion(
        "recordatorio_escalado_confirmacion", "confirmacion", "Recordatorio escalado de confirmación", "automatizacion",
        "Tasa de no-show", kpi_objetivo=4, metrica_paciente="no_show_recurrente",
        requiere_integracion=False,
        como_funciona="Manda recordatorios en varias tandas (ej. 48hs, 24hs, 2hs antes) y escala el canal si el paciente no responde.",
        beneficio="Baja el no-show sin depender de que un humano se acuerde de llamar — funciona igual un lunes que un feriado.",
    ),
    Intervencion(
        "proceso_recordar_protocolo", "confirmacion", "Recordar por protocolo (sin sistema)", "proceso",
        "Tasa de no-show", kpi_objetivo=4,
        durabilidad="Depende 100% de que el recepcionista no falle",
        requiere_integracion=False,
        como_funciona="Un protocolo escrito: recepción llama o escribe a cada paciente el día anterior, sin herramienta nueva.",
        beneficio="Cuesta cero implementar — pero se cae apenas el equipo está sobrecargado o alguien nuevo no conoce el protocolo.",
    ),
    Intervencion(
        "reprogramacion_automatica", "confirmacion", "Reprogramación automática ante cancelación", "automatizacion",
        "No-show / hora-sillón ociosa", kpi_objetivo=4, variable_objetivo="horas_sillon_disponibles",
        condicion="API de agenda con disponibilidad en tiempo real",
        requiere_integracion=True,
        como_funciona="Cuando un turno se cancela, ofrece automáticamente ese hueco a otros pacientes en lista de espera.",
        beneficio="Menos horas de sillón vacías por una cancelación de último momento.",
    ),
    Intervencion(
        "lista_espera_automatica", "confirmacion", "Lista de espera automática", "automatizacion",
        "Hora-sillón ociosa", variable_objetivo="horas_sillon_disponibles",
        condicion="API de agenda + registro de lista de espera",
        requiere_integracion=True,
        como_funciona="Mantiene una lista de pacientes que quieren un turno más temprano y los avisa apenas se libera un hueco.",
        beneficio="Llena huecos de agenda que hoy quedan vacíos por falta de seguimiento manual.",
    ),
    Intervencion(
        "instrucciones_preoperatorias", "confirmacion", "Instrucciones preoperatorias automáticas", "automatizacion",
        "Horas repetitivas", kpi_objetivo=15,
        condicion="Catálogo de tratamientos con instrucciones asociadas",
        requiere_integracion=False,
        como_funciona="Manda automáticamente las instrucciones previas al tratamiento (ayuno, medicación a suspender, etc.) según qué se va a hacer.",
        beneficio="El equipo deja de explicar lo mismo por teléfono cada vez, y el paciente llega mejor preparado.",
    ),
    Intervencion(
        "firma_digital_consentimientos", "confirmacion", "Firma digital de consentimientos", "automatizacion",
        "Horas administrativas", kpi_objetivo=15,
        condicion="Plataforma de firma digital integrada",
        requiere_compliance="Validez legal del consentimiento informado",
        requiere_integracion=True,
        como_funciona="El paciente firma el consentimiento informado desde el celular antes de llegar, en vez de hacerlo a mano en la sala de espera.",
        beneficio="Menos papeleo administrativo por consulta y menos tiempo de espera del lado del paciente.",
    ),

    # 4. Durante la consulta
    Intervencion(
        "transcripcion_historia_clinica", "consulta", "Transcripción automática de historia clínica", "ia",
        "Horas repetitivas del profesional", kpi_objetivo=15,
        condicion="Dictado integrado a la ficha",
        requiere_compliance="Dato de salud, Ley 25.326 (P53)",
        requiere_integracion=True,
        como_funciona="El profesional dicta durante la consulta y el sistema escribe la ficha automáticamente, en vez de tipear después.",
        beneficio="Menos tiempo administrativo del profesional después de cada consulta — más pacientes por día sin extender el horario.",
    ),
    Intervencion(
        "presupuesto_momento_ia", "consulta", "Generación de presupuesto en el momento (desde diagnóstico libre)", "ia",
        "Tasa de aceptación de presupuestos", kpi_objetivo=5,
        condicion="Catálogo de precios + integración con historia clínica",
        requiere_integracion=True,
        como_funciona="A partir de lo que el profesional escribió en la ficha, arma el presupuesto ahí mismo, sin que alguien lo tenga que calcular después.",
        beneficio="El paciente ve el número mientras todavía está en el consultorio, con el profesional presente para resolver dudas — mejor momento para aceptar.",
    ),
    Intervencion(
        "presupuesto_momento_menu", "consulta", "Generación de presupuesto en el momento (menú fijo)", "automatizacion",
        "Tasa de aceptación de presupuestos", kpi_objetivo=5,
        condicion="Catálogo de precios + integración con historia clínica",
        requiere_integracion=True,
        como_funciona="Igual que la versión con IA, pero el profesional elige el tratamiento de un menú fijo en vez de que el sistema lo infiera del diagnóstico.",
        beneficio="Mismo beneficio que la versión IA (presupuesto en el momento), con menos margen de error porque el profesional confirma el ítem exacto.",
    ),
    Intervencion(
        "aviso_demoras", "consulta", "Aviso automático de demoras", "automatizacion",
        "Horas repetitivas / tiempo administrativo", kpi_objetivo=15,
        condicion="Agenda en tiempo real",
        requiere_integracion=True,
        como_funciona="Si la agenda se atrasa, avisa automáticamente a los próximos pacientes en vez de que recepción llame uno por uno.",
        beneficio="Menos llamados manuales de recepción, y el paciente llega sabiendo que hay demora en vez de esperar sin información.",
    ),
    Intervencion(
        "proceso_checklist_verbal_cuidados", "consulta", "Checklist verbal de cuidados al cierre de la consulta", "proceso",
        "Horas repetitivas del profesional", kpi_objetivo=15,
        durabilidad="Depende de que el profesional recorra la lista completa cada vez, sin saltarse ítems por apuro entre turno y turno",
        requiere_integracion=False,
        como_funciona="Lista impresa pegada en el consultorio con los cuidados post-tratamiento más comunes; el profesional la recorre de memoria al cierre de cada consulta, sin ficha digital.",
        beneficio="Cuesta cero implementar — pero se degrada apenas hay apuro entre turnos y algún ítem queda afuera, cosa que con un envío automático no pasa.",
    ),
    Intervencion(
        "proceso_plantilla_papel_presupuesto", "consulta", "Plantilla en papel para armar el presupuesto en el momento", "proceso",
        "Tasa de aceptación de presupuestos", kpi_objetivo=5,
        durabilidad="Depende de que el profesional complete la plantilla a mano en cada consulta y no la posponga para \"después\"",
        requiere_integracion=False,
        como_funciona="Formulario en papel con los tratamientos y precios más comunes; el profesional lo completa a mano durante la consulta y se lo entrega al paciente ahí mismo.",
        beneficio="Cuesta cero implementar y da presupuesto en el momento igual que la versión digital — pero se pierde si el profesional lo deja para después y el paciente se va sin número.",
    ),

    # 5. Post-consulta / Seguimiento inmediato
    Intervencion(
        "instrucciones_postoperatorias", "post_consulta", "Instrucciones postoperatorias automáticas", "automatizacion",
        "Horas repetitivas", kpi_objetivo=15,
        condicion="Catálogo de tratamientos",
        requiere_integracion=False,
        como_funciona="Manda automáticamente los cuidados posteriores al tratamiento apenas termina la consulta.",
        beneficio="El equipo deja de repetir la misma explicación de cuidados turno tras turno.",
    ),
    Intervencion(
        "seguimiento_bienestar", "post_consulta", "Seguimiento de bienestar 24-48h", "ia",
        "Tasa de finalización / abandono", kpi_objetivo=7,
        condicion="Reglas claras de qué cuenta como alerta",
        requiere_integracion=False,
        como_funciona="Pregunta al paciente cómo se siente 24-48hs después del tratamiento y alerta al equipo si la respuesta indica un problema.",
        beneficio="Detecta complicaciones o pacientes insatisfechos antes de que abandonen el tratamiento en silencio.",
    ),
    Intervencion(
        "triage_urgencias", "post_consulta", "Asistente de triage de urgencias", "ia",
        "Tiempo de respuesta a urgencias", variable_objetivo="tiempo_respuesta_urgencias_min",
        condicion="Reglas de derivación explícitas, cero diagnóstico",
        requiere_compliance="P52 — comunicación con pacientes, nunca diagnostica",
        requiere_integracion=False,
        como_funciona="Cuando un paciente escribe con una urgencia, hace preguntas de derivación (nunca diagnostica) y prioriza el aviso al profesional de guardia.",
        beneficio="Las urgencias reales se atienden más rápido porque no se mezclan en la misma cola que una consulta administrativa.",
    ),
    Intervencion(
        "faq_conversacional", "post_consulta", "FAQ conversacional pre/post tratamiento", "ia",
        "Horas repetitivas del equipo", kpi_objetivo=15,
        condicion="Base de conocimiento de la clínica cargada",
        requiere_integracion=False,
        como_funciona="Responde las preguntas frecuentes de pacientes (horarios, precios generales, cuidados) sin que el equipo tenga que contestar siempre lo mismo.",
        beneficio="Libera tiempo del equipo de las preguntas repetitivas que no necesitan a una persona.",
    ),
    Intervencion(
        "proceso_llamado_48h_seguimiento", "post_consulta", "Llamado manual de seguimiento a las 48 horas", "proceso",
        "Tasa de finalización / abandono", kpi_objetivo=7,
        durabilidad="Depende de que alguien del equipo se acuerde de hacer la llamada 48hs después, sin agenda ni recordatorio automático",
        requiere_integracion=False,
        como_funciona="Protocolo escrito: alguien del equipo llama al paciente 48hs después de un tratamiento con un guion fijo de tres preguntas (cómo se siente, si tiene dudas, si necesita algo) y anota la respuesta a mano.",
        beneficio="Cuesta cero implementar y detecta pacientes insatisfechos antes de que abandonen el tratamiento — pero se cae apenas el equipo está sobrecargado y la llamada no se hace a tiempo.",
    ),

    # 6. Fidelización y Reactivación
    Intervencion(
        "reactivacion_inactivos", "fidelizacion", "Reactivación de pacientes inactivos", "automatizacion",
        "Tasa de reactivación", kpi_objetivo=9,
        metrica_paciente="porcentaje_base_inactiva",
        condicion="Base de pacientes con fecha de último control",
        requiere_integracion=False,
        como_funciona="Detecta pacientes que no vuelven hace tiempo y les manda una campaña de reactivación automática.",
        beneficio="Recupera pacientes que ya conocen la clínica en vez de gastar sólo en captar nuevos — suele ser más barato que adquisición.",
    ),
    Intervencion(
        "predictor_riesgo_no_show", "fidelizacion", "Predictor de riesgo de no-show", "ia",
        "Tasa de no-show", kpi_objetivo=4,
        metrica_paciente="no_show_recurrente",
        condicion="Historial de datos suficiente (clínica chica puede no tener volumen)",
        requiere_integracion=False,
        como_funciona="Identifica qué pacientes tienen historial de faltar y les aplica un seguimiento reforzado antes del turno.",
        beneficio="Distingue el problema real: 40 pacientes que faltaron una vez no es lo mismo que 6 que faltan siempre — cada uno necesita una intervención distinta.",
    ),
    Intervencion(
        "seguimiento_presupuestos_no_aceptados", "fidelizacion", "Seguimiento de presupuestos no aceptados", "automatizacion",
        "Tasa de aceptación de presupuestos", kpi_objetivo=5,
        metrica_paciente="velocidad_presupuesto_a_aceptacion",
        condicion="Presupuestos con fecha y estado registrados",
        requiere_integracion=False,
        como_funciona="Si un paciente recibió un presupuesto y no respondió, le hace seguimiento en el momento en que históricamente más conviene insistir.",
        beneficio="Recupera presupuestos que hoy quedan sin respuesta simplemente porque nadie volvió a preguntar.",
    ),
    Intervencion(
        "simulador_financiacion", "fidelizacion", "Simulador de financiación conversacional", "ia",
        "Tasa de aceptación de presupuestos", kpi_objetivo=5,
        condicion="Reglas de financiación cargadas",
        requiere_integracion=False,
        como_funciona="Le muestra al paciente opciones de cuotas/financiación para un presupuesto que le resultó caro.",
        beneficio="Un presupuesto rechazado por precio puede aceptarse igual si se ve como cuotas manejables.",
    ),
    Intervencion(
        "recordatorio_controles_periodicos", "fidelizacion", "Recordatorio de controles periódicos", "automatizacion",
        "Recall / retención", kpi_objetivo=8,
        metrica_paciente="intervalo_medio_entre_visitas",
        condicion="Fecha de próximo control registrada",
        requiere_integracion=False,
        como_funciona="Avisa automáticamente cuando le toca el control periódico a un paciente, en vez de esperar a que se acuerde solo.",
        beneficio="Sube el recall sin depender de que el paciente lleve la cuenta de cuándo fue su última visita.",
    ),
    Intervencion(
        "proceso_preagendar_control", "fidelizacion", "Pre-agendar el control antes de que el paciente se retire", "proceso",
        "Recall / retención", kpi_objetivo=8,
        durabilidad="Ninguna condición técnica, pero requiere disciplina de recepción",
        requiere_integracion=False,
        como_funciona="Recepción agenda el próximo control ahí mismo, antes de que el paciente se vaya de la clínica.",
        beneficio="Cuesta cero implementar — pero se pierde si recepción no lo hace sistemáticamente con cada paciente.",
    ),
    Intervencion(
        "campanas_estacionales_segmentadas", "fidelizacion", "Campañas estacionales segmentadas", "automatizacion",
        "Recall / reactivación", kpi_objetivo=9,
        metrica_paciente="estacionalidad_observada_por_paciente",
        condicion="Historial de tratamientos por paciente",
        requiere_integracion=False,
        como_funciona="Manda campañas ajustadas a la época del año y al tipo de tratamiento que cada paciente suele necesitar (ej. blanqueamiento antes de fiestas).",
        beneficio="Aprovecha los patrones estacionales reales de la clínica en vez de mandar la misma campaña todo el año.",
    ),

    # 7. Referidos y Reputación
    Intervencion(
        "pedido_automatico_resena", "referidos", "Pedido automático de reseña post-tratamiento", "automatizacion",
        "Reputación (no mapeado a un KPI — más bien adquisición)", kpi_objetivo=10,
        requiere_integracion=False,
        como_funciona="Manda un pedido de reseña automático unos días después del tratamiento, cuando el paciente ya está conforme con el resultado.",
        beneficio="Sube el volumen de reseñas sin que el equipo tenga que acordarse de pedirlas en cada caso.",
    ),
    Intervencion(
        "proceso_pedir_resena_verbal", "referidos", "Pedir la reseña verbalmente al cierre del turno", "proceso",
        "Reputación", kpi_objetivo=10,
        durabilidad="Ninguna condición técnica, depende de que el equipo se acuerde",
        requiere_integracion=False,
        como_funciona="El profesional o recepción pide la reseña de palabra al final del turno.",
        beneficio="Cuesta cero implementar — pero depende 100% de que alguien se acuerde de pedirla cada vez.",
    ),
    Intervencion(
        "programa_referidos_automatizado", "referidos", "Programa de referidos automatizado", "automatizacion",
        "Costo de adquisición vs. reactivación", kpi_objetivo=19,
        metrica_paciente="atribucion_referidos",
        condicion='Sistema de tracking "quién refirió a quién"',
        requiere_integracion=True,
        como_funciona="Registra quién refirió a quién y ofrece un incentivo automático cuando el referido efectivamente agenda.",
        beneficio="Un paciente referido suele costar mucho menos captar que uno de publicidad — esto lo hace sistemático en vez de espontáneo.",
    ),
    Intervencion(
        "monitoreo_resenas_negativas_alerta", "referidos", "Monitoreo de reseñas negativas (alerta simple)", "automatizacion",
        "Tiempo de respuesta a reclamos", variable_objetivo="tiempo_respuesta_reclamos_min",
        condicion="Acceso a API de Google Business/reviews",
        requiere_integracion=True,
        como_funciona="Avisa al equipo apenas aparece una reseña de 1-2 estrellas, sin esperar a que alguien la vea por casualidad.",
        beneficio="Una queja pública se responde en minutos, no en días — eso es lo que más pesa en cómo se ve la respuesta desde afuera.",
    ),
    Intervencion(
        "monitoreo_resenas_negativas_sentimiento", "referidos", "Monitoreo de reseñas negativas (analiza sentimiento)", "ia",
        "Tiempo de respuesta a reclamos", variable_objetivo="tiempo_respuesta_reclamos_min",
        condicion="Acceso a API de Google Business/reviews",
        requiere_integracion=True,
        como_funciona="Igual que la alerta simple, pero también lee reseñas de 3-4 estrellas que mencionan un problema aunque no sean negativas del todo.",
        beneficio="Detecta quejas disimuladas que una alerta por puntaje bajo se perdería.",
    ),
]

INTERVENCIONES_POR_ETAPA: dict[str, list[Intervencion]] = {
    etapa: [i for i in INTERVENCIONES if i.etapa == etapa] for etapa in ETAPAS
}


@dataclass
class Oportunidad:
    intervencion: Intervencion
    kpi_id: Optional[int]
    diagnostico: Diagnostico
    addressability: float  # 0-1: qué tan entregable es dado el contexto real de la clínica


# Heurística deliberadamente simple sobre texto libre (P44/P45 no son
# respuestas estructuradas) — documentado como tal, igual que el
# keyword-match de diagnostico.detectar_contradicciones.
_PALABRAS_INTEGRADO = ("conectado", "integrado", "mismo sistema", "todo en uno", "un solo sistema")
_PALABRAS_DESCONECTADO = ("separado", "no conectado", "no integrado", "cada uno por su lado", "planilla", "excel", "papel", "a mano")


def _requiere_integracion(condicion: str) -> bool:
    condicion = condicion.lower()
    return any(p in condicion for p in ("api", "integrad", "conectad", "sistema"))


def calcular_addressability(intervencion: Intervencion, respuestas_diagnostico: dict) -> float:
    """1.0 si la intervención no exige ninguna integración particular.
    Si exige API/integración, se cruza contra P45 ("¿están conectados los
    sistemas?"): favorable si el dueño ya declaró integración, penalizado
    si declaró sistemas sueltos, neutro (0.6) si no hay dato claro — nunca
    0 ni 1 sin evidencia, siguiendo el principio de no sobreafirmar.

    Fase I3: `intervencion.requiere_integracion` (declarado explícito) gana
    sobre el keyword-match de `condicion` cuando está presente — el
    keyword-match penalizaba por REDACCIÓN, no por mérito real (ver
    docstring del campo en la dataclass)."""
    requiere = intervencion.requiere_integracion
    if requiere is None:
        requiere = _requiere_integracion(intervencion.condicion)
    if not requiere:
        return 1.0
    p45 = (respuestas_diagnostico or {}).get("P45", "").lower()
    if any(p in p45 for p in _PALABRAS_INTEGRADO):
        return 1.0
    if any(p in p45 for p in _PALABRAS_DESCONECTADO):
        return 0.3
    return 0.6


def mapear_oportunidades(
    diagnosticos: list[Diagnostico], contexto_clinica: Optional[dict] = None,
) -> list[Oportunidad]:
    """Para cada diagnóstico con un problema real (nunca para HEALTHY ni
    INSUFFICIENT_EVIDENCE — no hay nada que recomendar en ninguno de los
    dos casos, por motivos opuestos), busca las intervenciones del
    catálogo que atacan ese KPI."""
    contexto_clinica = contexto_clinica or {}
    oportunidades = []
    for d in diagnosticos:
        if d.estado in (EstadoEvidencia.HEALTHY, EstadoEvidencia.INSUFFICIENT_EVIDENCE):
            continue
        for intervencion in INTERVENCIONES:
            # Fase I3: además del KPI principal, una intervención puede
            # atacar kpis_secundarios (ej. el agente 24/7 también baja el
            # tiempo de primera respuesta, no sólo sube la conversión).
            if intervencion.kpi_objetivo == d.kpi_id or d.kpi_id in intervencion.kpis_secundarios:
                oportunidades.append(Oportunidad(
                    intervencion=intervencion,
                    kpi_id=d.kpi_id,
                    diagnostico=d,
                    addressability=calcular_addressability(intervencion, contexto_clinica),
                ))
    return oportunidades
