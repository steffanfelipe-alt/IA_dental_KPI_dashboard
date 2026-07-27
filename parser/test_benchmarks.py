"""
test_benchmarks.py

Sin pytest (no está instalado en el entorno): corre con `python3 test_benchmarks.py`.
Criterios de aceptación del plan maestro de benchmarks + interpretación.
"""

import aranceles_com
from benchmarks import BENCHMARKS_AR, calcular_gap
from interpretacion import interpretar_kpi, peso_benchmark_vs_historial
from priorizacion import calcular_score, priorizar_kpis


def test_no_show_alto_es_desfavorable_no_favorable():
    # KPI 4 (no-show), mejor_es="menor": estar por ENCIMA del rango es malo.
    gap = calcular_gap(4, 28)
    assert gap.direccion == "por_encima"
    assert gap.favorable is False


def test_no_show_bajo_es_favorable():
    # KPI 4 (no-show), mejor_es="menor": estar por DEBAJO del rango es bueno.
    gap = calcular_gap(4, 3)
    assert gap.direccion == "por_debajo"
    assert gap.favorable is True


def test_aceptacion_alta_es_favorable():
    # KPI 5 (aceptación), mejor_es="mayor": estar por ENCIMA es bueno.
    gap = calcular_gap(5, 90)
    assert gap.direccion == "por_encima"
    assert gap.favorable is True


def test_kpis_sin_benchmark_nunca_comparan():
    for kpi_id in (7, 10, 19):
        assert BENCHMARKS_AR[kpi_id].confiabilidad == "sin_benchmark"
        gap = calcular_gap(kpi_id, 50)
        assert gap.tiene_benchmark is False
        assert gap.direccion == "sin_benchmark"
        assert gap.favorable is None

        resultado = interpretar_kpi(kpi_id, 50, respuestas_diagnostico={})
        payload = resultado["payload_enviado_al_asistente"]
        assert payload["gap"]["direccion"] == "sin_benchmark"
        assert payload["gap"]["tiene_benchmark"] is False
        assert "serie_historica_propia" in payload


def test_ticket_se_revaloriza_con_un_solo_numero():
    # KPI 6: rango 1.5-3 consultas, es_multiplo_arancel=True.
    original = aranceles_com.ARANCEL_COM["consulta"]
    try:
        aranceles_com.ARANCEL_COM["consulta"] = 30000
        gap = calcular_gap(6, 60000)  # exactamente 2 consultas al valor nuevo
        assert gap.direccion == "dentro_de_rango"

        aranceles_com.ARANCEL_COM["consulta"] = 100000
        gap2 = calcular_gap(6, 60000)  # ahora 0.6 consultas: por debajo del rango sano
        assert gap2.direccion == "por_debajo"
        assert gap2.favorable is False  # mejor_es="mayor" para el ticket
    finally:
        aranceles_com.ARANCEL_COM["consulta"] = original


def test_peso_benchmark_vs_historial():
    assert peso_benchmark_vs_historial(2) == {"benchmark": 0.8, "historial": 0.2}
    assert peso_benchmark_vs_historial(8) == {"benchmark": 0.5, "historial": 0.5}
    assert peso_benchmark_vs_historial(16) == {"benchmark": 0.2, "historial": 0.8}

    resultado = interpretar_kpi(4, 28, respuestas_diagnostico={}, semanas_de_datos_propios=2)
    assert resultado["payload_enviado_al_asistente"]["ponderacion"]["benchmark"] == 0.8
    resultado2 = interpretar_kpi(4, 28, respuestas_diagnostico={}, semanas_de_datos_propios=16)
    assert resultado2["payload_enviado_al_asistente"]["ponderacion"]["historial"] == 0.8


def test_proxy_internacional_rankea_debajo_de_oficial():
    # Dos gaps con la misma magnitud (ambos justo 50% por debajo del punto medio,
    # en dirección desfavorable) y el mismo impacto: el que tiene benchmark
    # "oficial" debe rankear por encima del que tiene "proxy_internacional".
    gap_oficial = calcular_gap(6, 1)          # ticket muy bajo -> por_debajo, desfavorable, oficial
    gap_proxy = calcular_gap(5, 10)           # aceptación muy baja -> por_debajo, desfavorable, proxy_internacional
    assert gap_oficial.benchmark.confiabilidad == "oficial"
    assert gap_proxy.benchmark.confiabilidad == "proxy_internacional"
    assert gap_oficial.favorable is False
    assert gap_proxy.favorable is False

    score_oficial = calcular_score(gap_oficial, impacto=1.0)
    score_proxy = calcular_score(gap_proxy, impacto=1.0)
    assert score_oficial > score_proxy

    top = priorizar_kpis([(gap_oficial, 1.0), (gap_proxy, 1.0)], top_n=2)
    assert top[0].kpi_id == 6
    assert top[1].kpi_id == 5


def test_priorizar_kpis_no_prioriza_gaps_favorables():
    gap_favorable = calcular_gap(5, 90)  # aceptación muy alta: favorable, no debería sumar score
    assert gap_favorable.favorable is True
    assert calcular_score(gap_favorable, impacto=10.0) == 0.0


def test_contexto_cualitativo_distinto_segun_respuestas():
    from interpretacion import construir_contexto_cualitativo

    sin_seguimiento = construir_contexto_cualitativo(
        {"P20": "No hacemos ningún seguimiento de los presupuestos."}, kpi_id=5,
    )
    con_seguimiento = construir_contexto_cualitativo(
        {"P20": "Hacemos seguimiento tres veces y aun así no aceptan."}, kpi_id=5,
    )
    assert sin_seguimiento != con_seguimiento
    assert "ningún seguimiento" in sin_seguimiento
    assert "tres veces" in con_seguimiento


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
