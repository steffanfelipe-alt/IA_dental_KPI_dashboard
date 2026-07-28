"""
test_coverage.py

Sin pytest: corre con `python3 test_coverage.py`.
Cubre la dimensión de período (serie por KPI, hallazgo 4) y que los
errores de fórmula queden registrados en vez de desaparecer en silencio
(hallazgo B).
"""

from coverage import VariableValue, evaluar_cobertura


def test_kpi_con_ambas_variables_con_serie_arma_serie_del_kpi():
    variables = {
        "turnos_agendados": VariableValue(
            73, "migracion_excel", 0.9,
            serie={"Enero 2026": 66.0, "Febrero 2026": 62.0}, periodo="Febrero 2026",
        ),
        "consultas_nuevas_mes": VariableValue(
            88, "migracion_excel", 0.9,
            serie={"Enero 2026": 95.0, "Febrero 2026": 88.0}, periodo="Febrero 2026",
        ),
    }
    resultado = evaluar_cobertura(variables)
    serie_kpi3 = resultado.kpis_calculados[3]["serie"]  # Tasa de agendamiento
    assert serie_kpi3 == {
        "Enero 2026": round(100 * 66 / 95, 1),
        "Febrero 2026": round(100 * 62 / 88, 1),
    }


def test_kpi_sin_serie_en_alguna_variable_no_arma_serie():
    variables = {
        "turnos_agendados": VariableValue(73, "migracion_excel", 0.9),  # sin serie
        "consultas_nuevas_mes": VariableValue(
            102, "migracion_excel", 0.9, serie={"Abril 2026": 102.0}, periodo="Abril 2026",
        ),
    }
    resultado = evaluar_cobertura(variables)
    assert resultado.kpis_calculados[3]["serie"] is None


def test_formula_que_falla_queda_en_kpis_con_error_no_desaparece():
    # horas_tarea_manual_semana con forma inesperada (float en vez de
    # dict) rompería kpi.calcular — no debe desaparecer sin dejar rastro.
    variables = {
        "horas_tarea_manual_semana": VariableValue(21.0, "migracion_excel", 0.8),
    }
    resultado = evaluar_cobertura(variables)
    assert 15 not in resultado.kpis_calculados
    assert 15 in resultado.kpis_con_error
    assert "AttributeError" in resultado.kpis_con_error[15]


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
