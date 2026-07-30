"""
test_periodos.py

Sin pytest: corre con `python3 test_periodos.py`.
Cubre la Fase 1 del plan de evolución: normalizar etiquetas de período a
una clave canónica, y el date binning que pide el punto 2 del doc de
deficiencias-parser-kpis.md.
"""

from periodos import agrupar_por_periodo, es_canonico, normalizar_periodo, orden_cronologico


def test_es_canonico_distingue_periodo_de_etiqueta_cualquiera():
    assert es_canonico("2026-04")
    assert es_canonico("2026-W18")
    # Los casos que rompían la serie de excel_parser:
    assert not es_canonico("TOTAL / Prom.")
    assert not es_canonico("Cobro = cobrado / facturado.")
    assert not es_canonico("Semana 1")
    assert not es_canonico("Abril 2026"), "es una etiqueta cruda, no la clave canónica"


def test_formatos_distintos_del_mismo_mes_normalizan_igual():
    esperado = "2026-04"
    for etiqueta in ("Abril 2026", "2026-04", "abr-26", "30-04-26", "abril de 2026"):
        assert normalizar_periodo(etiqueta) == esperado, f"{etiqueta!r} -> {normalizar_periodo(etiqueta)!r}"


def test_fechas_dia_mes_ano_caen_en_el_mismo_bucket_mensual():
    # El caso literal del doc de deficiencias, en formato día-mes-año
    # (convención Argentina): las tres caen en el mismo mes.
    fechas = ["2-5-25", "3-5-25", "7-5-25"]
    mensuales = {normalizar_periodo(f, "mes") for f in fechas}
    assert mensuales == {"2025-05"}, f"esperaba un solo mes, dio {mensuales!r}"


def test_fechas_de_la_misma_semana_iso_caen_en_el_mismo_bucket_semanal():
    # 2-5-25 y 3-5-25 son viernes y sábado de la misma semana ISO 18. La
    # granularidad "semana" es para el caso donde el KPI se mide semanal,
    # no mensual (ej. tiempo de respuesta).
    semanales = {normalizar_periodo(f, "semana") for f in ("2-5-25", "3-5-25")}
    assert semanales == {"2025-W18"}, f"esperaba la misma semana ISO, dio {semanales!r}"


def test_dia_mes_nunca_se_confunde_con_mes_dia():
    # "2-5-25" es 2 de mayo (día-mes-año), NUNCA 5 de febrero (mes-día-año)
    # — una planilla armada por una clínica argentina usa el formato local.
    assert normalizar_periodo("2-5-25") == "2025-05"


def test_etiqueta_irreconocible_devuelve_none():
    assert normalizar_periodo("¿?") is None
    assert normalizar_periodo("") is None


def test_orden_cronologico_ordena_por_clave_no_por_insercion():
    periodos = ["2026-04", "2026-01", "2026-03", "2026-02"]
    assert orden_cronologico(periodos) == ["2026-01", "2026-02", "2026-03", "2026-04"]


def test_fecha_con_hora_pegada_se_normaliza_igual_que_sin_hora():
    """Fase H4b: el bug real que dejaba `cobros_historico.csv` con un
    ledger vacío — `normalizar_periodo` rechazaba CUALQUIER fecha con
    componente de hora ("2024-08-03 09:30:00", el timestamp típico de un
    export crudo de un sistema real), no solo las de este caso puntual."""
    assert normalizar_periodo("2024-08-03 09:30:00") == "2024-08"
    assert normalizar_periodo("2024-08-03 09:30") == "2024-08"
    assert normalizar_periodo("30-04-2026 14:15:00") == "2026-04"


def test_agrupar_por_periodo_agrupa_registros_del_mismo_mes():
    registros = [
        {"fecha": "2-5-25", "valor": 90},
        {"fecha": "3-5-25", "valor": 80},
        {"fecha": "7-5-25", "valor": 100},
        {"fecha": "1-6-25", "valor": 70},
    ]
    grupos = agrupar_por_periodo(registros)
    assert set(grupos.keys()) == {"2025-05", "2025-06"}
    assert len(grupos["2025-05"]) == 3
    assert len(grupos["2025-06"]) == 1


def test_agrupar_por_periodo_no_descarta_fechas_irreconocibles():
    registros = [{"fecha": "2-5-25", "valor": 90}, {"fecha": "sin fecha", "valor": 10}]
    grupos = agrupar_por_periodo(registros)
    assert None in grupos, "una fecha irreconocible debe quedar visible, no desaparecer"
    assert len(grupos[None]) == 1


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
