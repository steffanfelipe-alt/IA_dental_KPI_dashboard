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


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
