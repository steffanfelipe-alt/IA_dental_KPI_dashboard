"""
test_formato.py

Sin pytest: corre con `python3 test_formato.py`.
Hallazgo 1.2 del informe de deficiencias: el agente devolvía números
crudos ("15000") en vez de formateados ("$15.000").
"""

from formato import fmt_ars, fmt_pct, fmt_horas, fmt_numero, fmt_por_unidad


def test_fmt_ars_separa_miles():
    assert fmt_ars(15000) == "$15.000"
    assert fmt_ars(5226666.67) == "$5.226.667"


def test_fmt_pct_usa_coma_decimal():
    assert fmt_pct(96.4) == "96,4%"


def test_fmt_horas():
    assert fmt_horas(21.0) == "21,0 hs"


def test_fmt_numero_none_no_rompe():
    assert fmt_numero(None) == "-"
    assert fmt_ars(None) == "-"
    assert fmt_pct(None) == "-"


def test_fmt_por_unidad_dict_formatea_cada_valor():
    resultado = fmt_por_unidad({"a": 1000000.0, "b": 2000000.0}, "$")
    assert resultado == "a: $1.000.000; b: $2.000.000"


def test_fmt_por_unidad_conteo():
    assert fmt_por_unidad(102, "conteo") == "102"


def test_fmt_por_unidad_reconoce_las_unidades_de_cruces_py():
    """Fase B: OPERACIONES_LEGALES (schema.py) usa "monto_ars" (vocabulario
    de MetricaInfo.unidad_dato), no "$" (vocabulario de KPIFormula.unidad)
    — deben formatearse igual que un monto en $."""
    assert fmt_por_unidad(104745.76, "monto_ars/unidad") == "$104.746"
    assert fmt_por_unidad(81315.79, "monto_ars/hora") == "$81.316"
    assert fmt_por_unidad(2660000, "monto_ars") == "$2.660.000"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
