"""
test_reconciliacion.py

Sin pytest: corre con `python -m parser.cobertura_calidad.test_reconciliacion`.
Reproduce el caso real verificado con evals: no_shows=57 (en vez de 16)
pasa todas las guardas de validacion.py pero implica una tasa de no-show
que no coincide con la que la propia planilla declara.
"""

from parser.cobertura_calidad.coverage import VariableValue
from parser.extraccion.excel_parser import TasaDeclarada
from parser.cobertura_calidad.reconciliacion import FUENTE_DERIVADA, reconciliar


def _vv(valor):
    return VariableValue(valor, "migracion_excel", 0.9)


def _tasas(**por_kpi) -> dict:
    """{"4": 21.9} -> {4: TasaDeclarada(vigente=21.9)}"""
    return {int(kpi): TasaDeclarada(vigente=valor) for kpi, valor in por_kpi.items()}


def test_no_show_mal_mapeado_se_detecta_y_se_pone_en_cuarentena():
    variables = {
        "no_shows": _vv(57),               # el bug real: debería ser 16
        "turnos_agendados": _vv(73),        # este SÍ es correcto (73)
        "consultas_nuevas_mes": _vv(102),   # correcto, corrobora KPI 3
    }
    # Tasa no-show declarada en la planilla: 21.9% (16/73). Tasa agenda
    # declarada: 71.6% (73/102) — coincide con lo ya extraído.
    tasas_declaradas = _tasas(**{"4": 21.9, "3": 71.6})

    a_cuarentena, discrepancias = reconciliar(variables, tasas_declaradas)

    assert "no_shows" in a_cuarentena
    assert "turnos_agendados" not in a_cuarentena  # corroborado por KPI 3, que sí cerró
    assert len(discrepancias) == 1
    assert discrepancias[0].kpi_id == 4


def test_todo_coincide_no_genera_cuarentena():
    variables = {"no_shows": _vv(16), "turnos_agendados": _vv(73)}
    tasas_declaradas = _tasas(**{"4": 21.9})
    a_cuarentena, discrepancias = reconciliar(variables, tasas_declaradas)
    assert a_cuarentena == set()
    assert discrepancias == []


def test_sin_tasas_declaradas_no_hace_nada():
    variables = {"no_shows": _vv(57), "turnos_agendados": _vv(73)}
    a_cuarentena, discrepancias = reconciliar(variables, {})
    assert a_cuarentena == set()
    assert discrepancias == []


def test_variable_faltante_no_rompe():
    variables = {"no_shows": _vv(57)}  # falta turnos_agendados
    a_cuarentena, discrepancias = reconciliar(variables, _tasas(**{"4": 21.9}))
    assert a_cuarentena == set()
    assert discrepancias == []


def test_dentro_de_tolerancia_no_marca_discrepancia():
    # 21.9% declarado vs 16.4/73=22.5% calculado: diferencia de 0.6pp, muy
    # por debajo de TOLERANCIA_PCT.
    variables = {"no_shows": _vv(16), "turnos_agendados": _vv(71)}
    tasas_declaradas = _tasas(**{"4": 21.9})  # calculado real: 100*16/71 = 22.5
    a_cuarentena, discrepancias = reconciliar(variables, tasas_declaradas)
    assert a_cuarentena == set()


def test_variable_derivada_no_corrobora_a_su_companera():
    # Circularidad: no_shows derivado de la tasa del KPI 4 satisface esa
    # identidad por construcción. Si el KPI 4 se dejara reconciliar,
    # cerraría siempre y daría por corroborado un turnos_agendados que
    # nunca se verificó — y eso lo salvaría de la cuarentena que le
    # corresponde por el KPI 3, que sí falla.
    variables = {
        # turnos_agendados MAL (real: 73). Rompe el KPI 3 contra su tasa.
        "turnos_agendados": _vv(150),
        "consultas_nuevas_mes": _vv(102),
        "no_shows": VariableValue(33, FUENTE_DERIVADA, 0.6),  # = 150 * 21.9%
    }
    tasas_declaradas = _tasas(**{"4": 21.9, "3": 71.6})

    a_cuarentena, discrepancias = reconciliar(variables, tasas_declaradas)

    # El KPI 4 no debe contarse como "cerrado" pese a dar exacto.
    assert 4 not in {d.kpi_id for d in discrepancias}
    assert 3 in {d.kpi_id for d in discrepancias}
    assert "turnos_agendados" in a_cuarentena


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
