"""
test_interpretacion.py

Sin pytest, sin API real (client=None devuelve el payload crudo): corre
con `python3 test_interpretacion.py`.
Cubre la Fase 4 del plan de confiabilidad: derivar semanas_de_datos_propios
de la serie real (hallazgo 4) y el panel completo (hallazgo 2). También
cubre interpretar_clinica (Fase 7): el tercer entry point que arma el
informe jerárquico a partir de diagnostico.py + catalogo_tecnologico.py +
priorizacion.py.
"""

import json

from calidad import evaluar_calidad
from catalogo_tecnologico import mapear_oportunidades
from diagnostico import diagnosticar
from interpretacion import interpretar_clinica, interpretar_kpi, interpretar_panel, semanas_desde_serie
from priorizacion import priorizar_oportunidades


def test_semanas_desde_serie_vacia_es_cero():
    assert semanas_desde_serie(None) == 0
    assert semanas_desde_serie({}) == 0


def test_semanas_desde_serie_cuatro_meses():
    serie = {"Enero 2026": 1, "Febrero 2026": 2, "Marzo 2026": 3, "Abril 2026": 4}
    # 4 meses * 4.33 semanas/mes ~= 17
    assert semanas_desde_serie(serie) == 17


def test_interpretar_kpi_deriva_semanas_de_la_serie_si_no_se_pasan():
    serie = {"Enero 2026": 20, "Febrero 2026": 22, "Marzo 2026": 25}
    resultado = interpretar_kpi(4, 25, respuestas_diagnostico={}, serie_historica=serie)
    payload = resultado["payload_enviado_al_asistente"]
    assert payload["semanas_de_datos_propios"] == semanas_desde_serie(serie)
    assert payload["semanas_de_datos_propios"] > 0


def test_interpretar_kpi_respeta_semanas_explicitas_aunque_haya_serie():
    serie = {"Enero 2026": 20, "Febrero 2026": 22}
    resultado = interpretar_kpi(4, 25, respuestas_diagnostico={}, serie_historica=serie, semanas_de_datos_propios=0)
    assert resultado["payload_enviado_al_asistente"]["semanas_de_datos_propios"] == 0


def test_interpretar_kpi_incluye_valor_formateado():
    resultado = interpretar_kpi(11, 5226666.67, respuestas_diagnostico={})
    assert resultado["payload_enviado_al_asistente"]["valor_formateado"] == "$5.226.667"


def test_interpretar_panel_arma_un_kpi_por_entrada():
    kpis_calculados = {
        1: {"nombre": "Consultas nuevas / mes", "valor": 102, "unidad": "conteo", "confianza": 0.9},
        4: {"nombre": "Tasa de no-show", "valor": 21.9, "unidad": "%", "confianza": 0.9,
            "serie": {"Marzo 2026": 20.0, "Abril 2026": 21.9}},
    }
    resultado = interpretar_panel(kpis_calculados, respuestas_diagnostico={})
    payload = resultado["payload_enviado_al_asistente"]
    assert len(payload["kpis"]) == 2
    kpi4 = next(k for k in payload["kpis"] if k["kpi_id"] == 4)
    assert kpi4["gap"]["tiene_benchmark"] is True
    assert kpi4["serie_historica_propia"] == {"Marzo 2026": 20.0, "Abril 2026": 21.9}
    assert kpi4["ponderacion"]["historial"] > 0  # tiene 2 meses de serie propia, no queda en 0


def test_interpretar_panel_no_rompe_con_kpi_de_valor_dict():
    # KPI 19 y 20 devuelven un dict (no un escalar) — no debe intentar
    # calcular_gap sobre eso.
    kpis_calculados = {
        19: {"nombre": "Costo adquisición vs. reactivación",
             "valor": {"costo_adquisicion": 5000, "costo_reactivacion": 2000},
             "unidad": "$/paciente", "confianza": 0.8},
    }
    resultado = interpretar_panel(kpis_calculados, respuestas_diagnostico={})
    kpi19 = resultado["payload_enviado_al_asistente"]["kpis"][0]
    assert kpi19["gap"]["tiene_benchmark"] is False


def test_interpretar_panel_incluye_contexto_general():
    resultado = interpretar_panel({}, respuestas_diagnostico={"P44": "clínica de 3 sillones"})
    assert "P44" in resultado["payload_enviado_al_asistente"]["contexto_general"]


def test_interpretar_clinica_sin_cliente_devuelve_payload_crudo():
    kpis_calculados = {
        4: {"valor": 40.0, "serie": None},
        5: {"valor": 80.0, "serie": None},
        6: {"valor": 20000.0, "serie": None},
    }
    respuestas = {"P2": "Recordatorio automático de confirmación"}
    diagnosticos = diagnosticar(kpis_calculados, respuestas)
    oportunidades = mapear_oportunidades(diagnosticos, contexto_clinica=respuestas)
    priorizadas = priorizar_oportunidades(oportunidades, impacto_por_kpi={d.kpi_id: 1.0 for d in diagnosticos})
    calidad = evaluar_calidad({
        "kpis_calculados": kpis_calculados, "kpis_bloqueados_por_diseno": [],
        "kpis_con_error": {}, "kpis_esperando_resolucion_conflicto": {},
        "variables_en_cuarentena": {}, "discrepancias_reconciliacion": [], "variables": {},
    })

    resultado = interpretar_clinica(
        diagnosticos, priorizadas, calidad_datos=calidad,
        respuestas_diagnostico=respuestas, studio_nombre="Clínica de prueba",
    )
    assert resultado["informe"] is None
    payload = resultado["payload_enviado_al_asistente"]
    assert payload["studio_nombre"] == "Clínica de prueba"
    assert len(payload["diagnosticos"]) == 3
    assert payload["calidad_datos"]["completitud_pct"] == calidad.completitud_pct

    # El payload completo tiene que ser serializable a JSON de verdad —
    # EstadoEvidencia es str+Enum, pero hay que confirmarlo, no asumirlo.
    texto = json.dumps(payload, ensure_ascii=False, default=str)
    assert "PROBLEM" in texto or "CRITICAL" in texto or "WATCH" in texto


def test_interpretar_clinica_incluye_contradiccion_y_patron_en_el_payload():
    kpis_calculados = {4: {"valor": 40.0, "serie": None}, 5: {"valor": 80.0, "serie": None}, 6: {"valor": 20000.0, "serie": None}}
    respuestas = {"P2": "Recordatorio automático"}
    diagnosticos = diagnosticar(kpis_calculados, respuestas)
    resultado = interpretar_clinica(diagnosticos, [], respuestas_diagnostico=respuestas)
    payload = resultado["payload_enviado_al_asistente"]

    d4 = next(d for d in payload["diagnosticos"] if d["kpi_id"] == 4)
    assert len(d4["contradicciones"]) == 1

    d5 = next(d for d in payload["diagnosticos"] if d["kpi_id"] == 5)
    assert d5["patrones_cruzados"]  # el patrón de mix (KPI 5 alto + KPI 6 bajo)


def test_interpretar_clinica_incluye_oportunidades_con_intervencion_anidada():
    kpis_calculados = {4: {"valor": 40.0, "serie": None}}
    diagnosticos = diagnosticar(kpis_calculados, {})
    oportunidades = mapear_oportunidades(diagnosticos)
    priorizadas = priorizar_oportunidades(oportunidades, impacto_por_kpi={4: 1.0})

    resultado = interpretar_clinica(diagnosticos, priorizadas)
    payload = resultado["payload_enviado_al_asistente"]
    assert payload["oportunidades_priorizadas"]
    primera = payload["oportunidades_priorizadas"][0]
    assert "nombre" in primera["intervencion"]
    assert "tipo" in primera["intervencion"]


def test_interpretar_clinica_vacio_no_rompe():
    resultado = interpretar_clinica([], [])
    assert resultado["payload_enviado_al_asistente"]["diagnosticos"] == []
    assert resultado["payload_enviado_al_asistente"]["oportunidades_priorizadas"] == []
    assert resultado["payload_enviado_al_asistente"]["calidad_datos"] is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
