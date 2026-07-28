"""
test_derivacion.py

Sin pytest: corre con `python3 test_derivacion.py`.
Cubre el punto 1 del plan: despejar una variable ausente desde la tasa que
la planilla ya trae calculada, sin adivinar nada y sin blanquear datos
rechazados.
"""

from coverage import VariableValue
from derivacion import CONFIANZA_DERIVADA, derivar_variables_faltantes
from extractors.excel_parser import TasaDeclarada
from reconciliacion import FUENTE_DERIVADA
from schema import KPI_BY_ID


def _vv(valor, serie=None):
    return VariableValue(valor, "migracion_excel", 0.9, archivo_origen="clinica.xlsx", serie=serie)


def test_despeja_no_shows_desde_la_tasa():
    # El caso motivador: la hoja trae "Tasa no-show" 21.9% y turnos=73,
    # pero ninguna columna con el conteo de ausencias. 73 * 21.9% = 15.99 -> 16.
    variables = {"turnos_agendados": _vv(73)}
    tasas = {4: TasaDeclarada(vigente=21.9)}

    nuevas, derivaciones = derivar_variables_faltantes(variables, tasas)

    assert nuevas["no_shows"].valor == 16.0
    assert nuevas["no_shows"].fuente == FUENTE_DERIVADA
    assert nuevas["no_shows"].confianza == CONFIANZA_DERIVADA
    assert derivaciones[0].variable == "no_shows"
    assert derivaciones[0].desde_denominador == "turnos_agendados"


def test_no_pisa_una_variable_ya_extraida():
    variables = {"turnos_agendados": _vv(73), "no_shows": _vv(16)}
    nuevas, derivaciones = derivar_variables_faltantes(variables, {4: TasaDeclarada(vigente=21.9)})
    assert nuevas == {}
    assert derivaciones == []


def test_sin_denominador_no_deriva():
    nuevas, derivaciones = derivar_variables_faltantes({}, {4: TasaDeclarada(vigente=21.9)})
    assert nuevas == {}


def test_kpi_sin_estructura_declarada_nunca_deriva():
    # KPI 10: numerador = resenas + referidos (suma de dos variables), así
    # que la tasa no determina un valor único. No declara numerador/
    # denominador y por lo tanto no debe derivar nada.
    assert KPI_BY_ID[10].numerador is None
    variables = {"pacientes_atendidos_periodo": _vv(100)}
    nuevas, _ = derivar_variables_faltantes(variables, {10: TasaDeclarada(vigente=8.0)})
    assert nuevas == {}


def test_solo_despeja_numerador_nunca_denominador():
    # Está el numerador pero falta el denominador: NO se despeja al revés
    # (den = num*100/tasa amplifica el error con tasas chicas).
    variables = {"no_shows": _vv(16)}
    nuevas, _ = derivar_variables_faltantes(variables, {4: TasaDeclarada(vigente=21.9)})
    assert "turnos_agendados" not in nuevas


def test_valor_derivado_invalido_se_descarta():
    # turnos negativos -> no_shows negativo -> validacion lo rechaza.
    variables = {"turnos_agendados": VariableValue(-73, "migracion_excel", 0.9)}
    nuevas, _ = derivar_variables_faltantes(variables, {4: TasaDeclarada(vigente=21.9)})
    assert nuevas == {}


def test_deriva_la_serie_completa_por_periodo():
    variables = {"turnos_agendados": _vv(73, serie={"Marzo 2026": 79.0, "Abril 2026": 73.0})}
    tasas = {4: TasaDeclarada(vigente=21.9, serie={"Marzo 2026": 21.5, "Abril 2026": 21.9})}

    nuevas, _ = derivar_variables_faltantes(variables, tasas)

    assert nuevas["no_shows"].serie == {"Marzo 2026": 17.0, "Abril 2026": 16.0}
    assert nuevas["no_shows"].periodo == "Abril 2026"


def test_serie_solo_sobre_periodos_en_comun():
    variables = {"turnos_agendados": _vv(73, serie={"Enero 2026": 66.0, "Abril 2026": 73.0})}
    tasas = {4: TasaDeclarada(vigente=21.9, serie={"Abril 2026": 21.9})}
    nuevas, _ = derivar_variables_faltantes(variables, tasas)
    assert list(nuevas["no_shows"].serie) == ["Abril 2026"]


def test_sin_serie_en_la_tasa_deriva_solo_el_escalar():
    variables = {"turnos_agendados": _vv(73, serie={"Abril 2026": 73.0})}
    nuevas, _ = derivar_variables_faltantes(variables, {4: TasaDeclarada(vigente=21.9)})
    assert nuevas["no_shows"].valor == 16.0
    assert nuevas["no_shows"].serie is None


def test_monto_derivado_no_se_redondea_a_entero():
    # monto_cobrado es float: conserva decimales, a diferencia de un conteo.
    variables = {"monto_facturado": _vv(5510000.0)}
    nuevas, _ = derivar_variables_faltantes(variables, {13: TasaDeclarada(vigente=96.6)})
    assert nuevas["monto_cobrado"].valor == round(5510000.0 * 0.966, 2)


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
