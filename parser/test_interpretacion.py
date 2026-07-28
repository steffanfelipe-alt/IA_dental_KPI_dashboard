"""
test_interpretacion.py

Sin pytest, sin API real (client=None devuelve el payload crudo): corre
con `python3 test_interpretacion.py`.
Cubre la Fase 4 del plan de confiabilidad: derivar semanas_de_datos_propios
de la serie real (hallazgo 4) y el panel completo (hallazgo 2).
"""

from interpretacion import interpretar_kpi, interpretar_panel, semanas_desde_serie


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


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
