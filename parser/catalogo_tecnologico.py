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
   v2 ya incluye 3 alternativas de proceso (🅿️) con su propia debilidad
   documentada en `durabilidad` — condición cero, pero depende de que un
   humano no falle.
2. **`periodo_evaluacion_semanas`**: NO se completa acá — es el único
   campo que sigue pendiente del usuario (cuántas semanas antes de medir
   si una intervención movió el KPI). Queda en `None` hasta confirmarlo.
3. **`kpi_objetivo` / `variable_objetivo` / `metrica_paciente`**: derivado
   del cruce contra schema.py — ver la nota de "4 métricas sin KPI" más
   abajo.

## Hallazgo: 4 métricas objetivo del catálogo no tenían KPI que las mida

Cruzando las métricas objetivo del catálogo contra los 20 KPIs de
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

from diagnostico import Diagnostico, EstadoEvidencia


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
    periodo_evaluacion_semanas: Optional[int] = None  # pendiente de confirmar con el usuario
    durabilidad: Optional[str] = None  # solo alternativas de proceso: su debilidad conocida


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
    ),
    Intervencion(
        "calificador_leads_reglas", "captacion", "Calificador automático de leads (reglas fijas)", "automatizacion",
        "Tasa de conversión lead→turno", kpi_objetivo=3,
        condicion="Ninguna especial (corre sobre WhatsApp)",
    ),
    Intervencion(
        "calificador_leads_ia", "captacion", "Calificador automático de leads (interpreta texto libre)", "ia",
        "Tasa de conversión lead→turno", kpi_objetivo=3,
        condicion="Ninguna especial (corre sobre WhatsApp)",
    ),
    Intervencion(
        "retargeting_formularios", "captacion", "Retargeting de formularios abandonados", "automatizacion",
        "Tiempo de primera respuesta", kpi_objetivo=2,
        condicion="Necesita tracking/webhook en la landing",
    ),

    # 2. Conversión / Agendamiento
    Intervencion(
        "agente_agendamiento_24_7", "conversion", "Agente de agendamiento 24/7", "ia",
        "Tasa de conversión a turno agendado", kpi_objetivo=3,
        condicion="API contra la agenda real de la clínica (lo que preguntan P44/P45)",
    ),
    Intervencion(
        "seguimiento_leads_sin_confirmar", "conversion", "Seguimiento a leads sin confirmar", "automatizacion",
        "Tiempo de primera respuesta", kpi_objetivo=2,
    ),
    Intervencion(
        "presupuesto_estimado_tabla", "conversion", "Presupuesto estimado automático (tabla fija)", "automatizacion",
        "Tasa de aceptación de presupuestos (indirecta)", kpi_objetivo=5,
        condicion="Lista de precios digitalizada",
    ),
    Intervencion(
        "presupuesto_estimado_ia", "conversion", "Presupuesto estimado automático (personalizado)", "ia",
        "Tasa de aceptación de presupuestos (indirecta)", kpi_objetivo=5,
        condicion="Lista de precios digitalizada",
    ),
    Intervencion(
        "recordatorio_documentacion_previa", "conversion", "Recordatorio de documentación previa", "automatizacion",
        "Horas repetitivas del equipo", kpi_objetivo=15,
    ),

    # 3. Confirmación y Pre-consulta
    Intervencion(
        "recordatorio_escalado_confirmacion", "confirmacion", "Recordatorio escalado de confirmación", "automatizacion",
        "Tasa de no-show", kpi_objetivo=4, metrica_paciente="no_show_recurrente",
    ),
    Intervencion(
        "proceso_recordar_protocolo", "confirmacion", "Recordar por protocolo (sin sistema)", "proceso",
        "Tasa de no-show", kpi_objetivo=4,
        durabilidad="Depende 100% de que el recepcionista no falle",
    ),
    Intervencion(
        "reprogramacion_automatica", "confirmacion", "Reprogramación automática ante cancelación", "automatizacion",
        "No-show / hora-sillón ociosa", kpi_objetivo=4, variable_objetivo="horas_sillon_disponibles",
        condicion="API de agenda con disponibilidad en tiempo real",
    ),
    Intervencion(
        "lista_espera_automatica", "confirmacion", "Lista de espera automática", "automatizacion",
        "Hora-sillón ociosa", variable_objetivo="horas_sillon_disponibles",
        condicion="API de agenda + registro de lista de espera",
    ),
    Intervencion(
        "instrucciones_preoperatorias", "confirmacion", "Instrucciones preoperatorias automáticas", "automatizacion",
        "Horas repetitivas", kpi_objetivo=15,
        condicion="Catálogo de tratamientos con instrucciones asociadas",
    ),
    Intervencion(
        "firma_digital_consentimientos", "confirmacion", "Firma digital de consentimientos", "automatizacion",
        "Horas administrativas", kpi_objetivo=15,
        condicion="Plataforma de firma digital integrada",
        requiere_compliance="Validez legal del consentimiento informado",
    ),

    # 4. Durante la consulta
    Intervencion(
        "transcripcion_historia_clinica", "consulta", "Transcripción automática de historia clínica", "ia",
        "Horas repetitivas del profesional", kpi_objetivo=15,
        condicion="Dictado integrado a la ficha",
        requiere_compliance="Dato de salud, Ley 25.326 (P53)",
    ),
    Intervencion(
        "presupuesto_momento_ia", "consulta", "Generación de presupuesto en el momento (desde diagnóstico libre)", "ia",
        "Tasa de aceptación de presupuestos", kpi_objetivo=5,
        condicion="Catálogo de precios + integración con historia clínica",
    ),
    Intervencion(
        "presupuesto_momento_menu", "consulta", "Generación de presupuesto en el momento (menú fijo)", "automatizacion",
        "Tasa de aceptación de presupuestos", kpi_objetivo=5,
        condicion="Catálogo de precios + integración con historia clínica",
    ),
    Intervencion(
        "aviso_demoras", "consulta", "Aviso automático de demoras", "automatizacion",
        "Horas repetitivas / tiempo administrativo", kpi_objetivo=15,
        condicion="Agenda en tiempo real",
    ),

    # 5. Post-consulta / Seguimiento inmediato
    Intervencion(
        "instrucciones_postoperatorias", "post_consulta", "Instrucciones postoperatorias automáticas", "automatizacion",
        "Horas repetitivas", kpi_objetivo=15,
        condicion="Catálogo de tratamientos",
    ),
    Intervencion(
        "seguimiento_bienestar", "post_consulta", "Seguimiento de bienestar 24-48h", "ia",
        "Tasa de finalización / abandono", kpi_objetivo=7,
        condicion="Reglas claras de qué cuenta como alerta",
    ),
    Intervencion(
        "triage_urgencias", "post_consulta", "Asistente de triage de urgencias", "ia",
        "Tiempo de respuesta a urgencias", variable_objetivo="tiempo_respuesta_urgencias_min",
        condicion="Reglas de derivación explícitas, cero diagnóstico",
        requiere_compliance="P52 — comunicación con pacientes, nunca diagnostica",
    ),
    Intervencion(
        "faq_conversacional", "post_consulta", "FAQ conversacional pre/post tratamiento", "ia",
        "Horas repetitivas del equipo", kpi_objetivo=15,
        condicion="Base de conocimiento de la clínica cargada",
    ),

    # 6. Fidelización y Reactivación
    Intervencion(
        "reactivacion_inactivos", "fidelizacion", "Reactivación de pacientes inactivos", "automatizacion",
        "Tasa de reactivación", kpi_objetivo=9,
        metrica_paciente="porcentaje_base_inactiva",
        condicion="Base de pacientes con fecha de último control",
    ),
    Intervencion(
        "predictor_riesgo_no_show", "fidelizacion", "Predictor de riesgo de no-show", "ia",
        "Tasa de no-show", kpi_objetivo=4,
        metrica_paciente="no_show_recurrente",
        condicion="Historial de datos suficiente (clínica chica puede no tener volumen)",
    ),
    Intervencion(
        "seguimiento_presupuestos_no_aceptados", "fidelizacion", "Seguimiento de presupuestos no aceptados", "automatizacion",
        "Tasa de aceptación de presupuestos", kpi_objetivo=5,
        metrica_paciente="velocidad_presupuesto_a_aceptacion",
        condicion="Presupuestos con fecha y estado registrados",
    ),
    Intervencion(
        "simulador_financiacion", "fidelizacion", "Simulador de financiación conversacional", "ia",
        "Tasa de aceptación de presupuestos", kpi_objetivo=5,
        condicion="Reglas de financiación cargadas",
    ),
    Intervencion(
        "recordatorio_controles_periodicos", "fidelizacion", "Recordatorio de controles periódicos", "automatizacion",
        "Recall / retención", kpi_objetivo=8,
        metrica_paciente="intervalo_medio_entre_visitas",
        condicion="Fecha de próximo control registrada",
    ),
    Intervencion(
        "proceso_preagendar_control", "fidelizacion", "Pre-agendar el control antes de que el paciente se retire", "proceso",
        "Recall / retención", kpi_objetivo=8,
        durabilidad="Ninguna condición técnica, pero requiere disciplina de recepción",
    ),
    Intervencion(
        "campanas_estacionales_segmentadas", "fidelizacion", "Campañas estacionales segmentadas", "automatizacion",
        "Recall / reactivación", kpi_objetivo=9,
        metrica_paciente="estacionalidad_observada_por_paciente",
        condicion="Historial de tratamientos por paciente",
    ),

    # 7. Referidos y Reputación
    Intervencion(
        "pedido_automatico_resena", "referidos", "Pedido automático de reseña post-tratamiento", "automatizacion",
        "Reputación (no mapeado a un KPI — más bien adquisición)", kpi_objetivo=10,
    ),
    Intervencion(
        "proceso_pedir_resena_verbal", "referidos", "Pedir la reseña verbalmente al cierre del turno", "proceso",
        "Reputación", kpi_objetivo=10,
        durabilidad="Ninguna condición técnica, depende de que el equipo se acuerde",
    ),
    Intervencion(
        "programa_referidos_automatizado", "referidos", "Programa de referidos automatizado", "automatizacion",
        "Costo de adquisición vs. reactivación", kpi_objetivo=19,
        metrica_paciente="atribucion_referidos",
        condicion='Sistema de tracking "quién refirió a quién"',
    ),
    Intervencion(
        "monitoreo_resenas_negativas_alerta", "referidos", "Monitoreo de reseñas negativas (alerta simple)", "automatizacion",
        "Tiempo de respuesta a reclamos", variable_objetivo="tiempo_respuesta_reclamos_min",
        condicion="Acceso a API de Google Business/reviews",
    ),
    Intervencion(
        "monitoreo_resenas_negativas_sentimiento", "referidos", "Monitoreo de reseñas negativas (analiza sentimiento)", "ia",
        "Tiempo de respuesta a reclamos", variable_objetivo="tiempo_respuesta_reclamos_min",
        condicion="Acceso a API de Google Business/reviews",
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
    0 ni 1 sin evidencia, siguiendo el principio de no sobreafirmar."""
    if not _requiere_integracion(intervencion.condicion):
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
            if intervencion.kpi_objetivo == d.kpi_id:
                oportunidades.append(Oportunidad(
                    intervencion=intervencion,
                    kpi_id=d.kpi_id,
                    diagnostico=d,
                    addressability=calcular_addressability(intervencion, contexto_clinica),
                ))
    return oportunidades
