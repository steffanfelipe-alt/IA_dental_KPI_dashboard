"""
test_catalogo_tecnologico.py

Sin pytest: corre con `python3 test_catalogo_tecnologico.py`.
Cubre catalogo_tecnologico.py (Fase 5): integridad del catálogo (cada
kpi_objetivo/variable_objetivo referencia algo real de schema.py),
addressability condicional, y que mapear_oportunidades solo proponga
intervenciones para diagnósticos con un problema real.
"""

from catalogo_tecnologico import (
    ETAPAS,
    INTERVENCIONES,
    INTERVENCIONES_POR_ETAPA,
    SEMANAS_EVALUACION_POR_TIPO,
    Intervencion,
    calcular_addressability,
    mapear_oportunidades,
)
from diagnostico import Diagnostico, EstadoEvidencia
from schema import KPI_BY_ID, VARIABLE_TYPES


def _diagnostico(kpi_id, estado):
    return Diagnostico(
        kpi_id=kpi_id, problema="x", estado=estado, hechos=[], anomalias=[],
        hipotesis=[], contradicciones=[], patrones_cruzados=[],
        informacion_faltante=[], confianza=1.0,
    )


# ---------------------------------------------------------------------------
# Integridad del catálogo
# ---------------------------------------------------------------------------

def test_toda_etapa_tiene_al_menos_una_intervencion():
    for etapa in ETAPAS:
        assert INTERVENCIONES_POR_ETAPA[etapa], f"{etapa} no tiene ninguna intervención"


def test_ids_de_intervencion_son_unicos():
    ids = [i.id for i in INTERVENCIONES]
    assert len(ids) == len(set(ids)), "hay ids de intervención duplicados"


def test_todo_kpi_objetivo_referencia_un_kpi_real():
    for i in INTERVENCIONES:
        if i.kpi_objetivo is not None:
            assert i.kpi_objetivo in KPI_BY_ID, f"{i.id}: KPI {i.kpi_objetivo} no existe"


def test_toda_variable_objetivo_referencia_una_variable_real():
    for i in INTERVENCIONES:
        if i.variable_objetivo is not None:
            assert i.variable_objetivo in VARIABLE_TYPES, f"{i.id}: variable {i.variable_objetivo!r} no existe en schema.py"


def test_intervenciones_con_dato_de_salud_declaran_compliance():
    con_compliance = {"transcripcion_historia_clinica", "triage_urgencias", "firma_digital_consentimientos"}
    for id_ in con_compliance:
        intervencion = next(i for i in INTERVENCIONES if i.id == id_)
        assert intervencion.requiere_compliance, f"{id_} debería declarar requiere_compliance"


def test_tipo_condicional_del_catalogo_v1_quedo_partido_en_dos_entradas():
    # "automatización si son opciones fijas / IA si interpreta texto libre"
    # se partió en dos intervenciones de catálogo, no un tipo ambiguo.
    tipos_calificador = {i.tipo for i in INTERVENCIONES if i.id.startswith("calificador_leads")}
    assert tipos_calificador == {"automatizacion", "ia"}


def test_alternativas_de_proceso_declaran_su_debilidad():
    procesos = [i for i in INTERVENCIONES if i.tipo == "proceso"]
    assert len(procesos) == 9
    for p in procesos:
        assert p.durabilidad, f"{p.id}: una alternativa de proceso debería declarar su debilidad conocida"


# ---------------------------------------------------------------------------
# Addressability
# ---------------------------------------------------------------------------

def test_sin_condicion_especial_addressability_es_uno():
    intervencion = next(i for i in INTERVENCIONES if i.id == "recordatorio_escalado_confirmacion")
    assert calcular_addressability(intervencion, {}) == 1.0


def test_requiere_integracion_y_clinica_declara_integrada():
    intervencion = next(i for i in INTERVENCIONES if i.id == "agente_agendamiento_24_7")
    assert calcular_addressability(intervencion, {"P45": "Sí, todo está conectado en un solo sistema"}) == 1.0


def test_requiere_integracion_y_clinica_declara_desconectada():
    intervencion = next(i for i in INTERVENCIONES if i.id == "agente_agendamiento_24_7")
    assert calcular_addressability(intervencion, {"P45": "Usamos una planilla de Excel aparte"}) == 0.3


def test_requiere_integracion_sin_dato_es_neutro():
    intervencion = next(i for i in INTERVENCIONES if i.id == "agente_agendamiento_24_7")
    assert calcular_addressability(intervencion, {}) == 0.6


# ---------------------------------------------------------------------------
# mapear_oportunidades
# ---------------------------------------------------------------------------

def test_mapear_oportunidades_solo_para_problemas_reales():
    diagnosticos = [
        _diagnostico(4, EstadoEvidencia.HEALTHY),
        _diagnostico(7, EstadoEvidencia.INSUFFICIENT_EVIDENCE),
    ]
    assert mapear_oportunidades(diagnosticos) == []


def test_mapear_oportunidades_encuentra_intervenciones_del_kpi_correcto():
    diagnosticos = [_diagnostico(4, EstadoEvidencia.CRITICAL)]
    oportunidades = mapear_oportunidades(diagnosticos)
    ids = {o.intervencion.id for o in oportunidades}
    assert "recordatorio_escalado_confirmacion" in ids
    assert "proceso_recordar_protocolo" in ids
    assert "reprogramacion_automatica" in ids
    assert "predictor_riesgo_no_show" in ids
    assert all(o.kpi_id == 4 for o in oportunidades)


def test_mapear_oportunidades_incluye_addressability_por_contexto():
    diagnosticos = [_diagnostico(3, EstadoEvidencia.PROBLEM)]  # agente_agendamiento_24_7 apunta acá
    oportunidades = mapear_oportunidades(diagnosticos, contexto_clinica={"P45": "Usamos una planilla aparte para la agenda"})
    agente = next(o for o in oportunidades if o.intervencion.id == "agente_agendamiento_24_7")
    assert agente.addressability == 0.3


# ---------------------------------------------------------------------------
# Fase H2: periodo_evaluacion_semanas — el único campo que quedaba
# esperando confirmación del usuario, ahora derivado de `tipo`.
# ---------------------------------------------------------------------------

def test_las_45_intervenciones_tienen_periodo_de_evaluacion_poblado():
    assert len(INTERVENCIONES) == 45
    sin_poblar = [i.id for i in INTERVENCIONES if i.periodo_evaluacion_semanas is None]
    assert sin_poblar == []


def test_periodo_de_evaluacion_corresponde_al_tipo():
    for i in INTERVENCIONES:
        assert i.periodo_evaluacion_semanas == SEMANAS_EVALUACION_POR_TIPO[i.tipo], i.id


def test_periodo_de_evaluacion_explicito_no_se_pisa():
    intervencion = Intervencion(
        "x", "captacion", "test", "proceso", "metrica", periodo_evaluacion_semanas=99,
    )
    assert intervencion.periodo_evaluacion_semanas == 99


# ---------------------------------------------------------------------------
# Fase I3: el chatbot dejó de quedar sistemáticamente último para KPI 2 —
# ni por keyword-match injusto (requiere_integracion explícito) ni porque
# el catálogo tenía dos intervenciones mal etiquetadas compitiendo con él.
# ---------------------------------------------------------------------------

def test_chatbot_ya_no_compite_con_intervenciones_mal_etiquetadas_en_kpi_2():
    """Antes de I3, retargeting_formularios y seguimiento_leads_sin_confirmar
    también apuntaban a kpi_objetivo=2 y ganaban por addressability más
    alto (un artefacto de redacción) — el chatbot quedaba sistemáticamente
    tercero. Reetiquetadas a KPI 3 (que es lo que de verdad mueven), sólo
    quedan para KPI 2 las dos intervenciones que genuinamente son de
    primera respuesta: el chatbot y el agente 24/7 (vía kpi secundario)."""
    diagnosticos = [_diagnostico(2, EstadoEvidencia.PROBLEM)]
    oportunidades = mapear_oportunidades(diagnosticos)
    ids = {o.intervencion.id for o in oportunidades}
    assert ids == {"chatbot_captacion_redes", "agente_agendamiento_24_7"}
    assert "retargeting_formularios" not in ids
    assert "seguimiento_leads_sin_confirmar" not in ids


def test_agente_24_7_aparece_para_su_kpi_principal_y_para_el_secundario():
    """El agente de agendamiento 24/7 no sólo sube la conversión (KPI 3,
    su kpi_objetivo) — al responder al instante también baja el tiempo de
    primera respuesta (KPI 2, declarado en kpis_secundarios)."""
    for kpi_id in (2, 3):
        diagnosticos = [_diagnostico(kpi_id, EstadoEvidencia.PROBLEM)]
        oportunidades = mapear_oportunidades(diagnosticos)
        ids = [o.intervencion.id for o in oportunidades]
        assert "agente_agendamiento_24_7" in ids, f"no apareció para KPI {kpi_id}"


def test_requiere_integracion_explicito_gana_al_keyword_match():
    """retargeting_formularios declara requiere_integracion=True aunque su
    condicion ("Necesita tracking/webhook en la landing") no contiene
    ninguna palabra del keyword-match viejo ("api"/"integrad"/"conectad"/
    "sistema") — antes de I3 esto le daba addressability=1.0 de forma
    injusta frente al chatbot, que sí tiene "API" en el texto."""
    intervencion = next(i for i in INTERVENCIONES if i.id == "retargeting_formularios")
    assert intervencion.requiere_integracion is True
    assert calcular_addressability(intervencion, {}) == 0.6  # neutro, no 1.0


def test_intervencion_sin_requiere_integracion_declarado_cae_al_keyword_match():
    """Retrocompatibilidad: una intervención con requiere_integracion=None
    (default) sigue usando el keyword-match de siempre sobre `condicion`."""
    intervencion = Intervencion(
        "x", "captacion", "test", "proceso", "metrica",
        condicion="Acceso a API de un sistema externo",
    )
    assert intervencion.requiere_integracion is None
    assert calcular_addressability(intervencion, {}) == 0.6  # keyword "api" matchea


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
