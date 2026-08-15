"""
test_coverage.py

Sin pytest: corre con `python -m parser.cobertura_calidad.test_coverage`.
Cubre la dimensión de período (serie por KPI, hallazgo 4) y que los
errores de fórmula queden registrados en vez de desaparecer en silencio
(hallazgo B).
"""

import pandas as pd

from parser.cobertura_calidad.coverage import VariableValue, evaluar_cobertura
from parser.extraccion.excel_parser import aplicar_mapeo
from parser.vocabulario.schema import KPI_FORMULAS


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


def test_periodo_con_denominador_cero_no_queda_como_none_en_la_serie():
    # Bug real (encontrado probando con datos reales vía Streamlit): un
    # mes sin consultas_nuevas_mes da denominador 0 -> _pct devuelve None
    # para ESE período. Antes del fix, ese None quedaba guardado en
    # serie_kpi y agregados.calcular_agregado(..., "ultimo") explotaba si
    # justo era el período más reciente. El período debe faltar de la
    # serie, no aparecer con valor None.
    variables = {
        "turnos_agendados": VariableValue(
            73, "migracion_excel", 0.9,
            serie={"2026-01": 66.0, "2026-02": 62.0, "2026-03": 0.0}, periodo="2026-03",
        ),
        "consultas_nuevas_mes": VariableValue(
            0, "migracion_excel", 0.9,
            serie={"2026-01": 95.0, "2026-02": 88.0, "2026-03": 0.0}, periodo="2026-03",
        ),
    }
    resultado = evaluar_cobertura(variables)
    serie_kpi3 = resultado.kpis_calculados[3]["serie"]
    assert "2026-03" not in serie_kpi3, "el período con denominador 0 no debe colarse como None"
    assert serie_kpi3 == {"2026-01": round(100 * 66 / 95, 1), "2026-02": round(100 * 62 / 88, 1)}

    # Y el agregado "ultimo" no explota: salta al último período real.
    assert resultado.kpis_calculados[3]["agregados"]["ultimo"] == round(100 * 62 / 88, 1)


def test_serie_de_kpi_intersecta_entre_archivos_con_etiquetas_de_periodo_distintas():
    # El hueco real que motivó la Fase 1 (periodos.py): antes de
    # normalizar, un archivo etiquetando "Marzo 2026"/"Abril 2026" y otro
    # "2026-03"/"2026-04" no intersectaban nunca — _calcular_serie_kpi
    # devolvía None en silencio aunque ambas variables tuvieran serie.
    df_texto = pd.DataFrame({"mes": ["Marzo 2026", "Abril 2026"], "turnos": [79, 73]})
    variables = aplicar_mapeo(df_texto, {
        "hoja": "ConsultorioA", "fila_encabezado": 0,
        "orientacion": "periodos_en_filas", "columna_periodo": 0,
        "mapeo": [{"columna_index": 1, "variable": "turnos_agendados", "agregacion": "sum", "confianza": 0.9}],
    })
    df_iso = pd.DataFrame({"periodo": ["2026-03", "2026-04"], "consultas": [110, 102]})
    variables = aplicar_mapeo(df_iso, {
        "hoja": "ConsultorioB", "fila_encabezado": 0,
        "orientacion": "periodos_en_filas", "columna_periodo": 0,
        "mapeo": [{"columna_index": 1, "variable": "consultas_nuevas_mes", "agregacion": "sum", "confianza": 0.9}],
    }, variables)

    resultado = evaluar_cobertura(variables)
    serie_kpi3 = resultado.kpis_calculados[3]["serie"]  # Tasa de agendamiento
    assert serie_kpi3 is not None, "las series deberían intersectar una vez normalizados los períodos"
    assert serie_kpi3 == {"2026-03": round(100 * 79 / 110, 1), "2026-04": round(100 * 73 / 102, 1)}

    # Y de yapa: los agregados de la Fase 1 quedan disponibles al lado de "valor".
    agregados = resultado.kpis_calculados[3]["agregados"]
    assert agregados["promedio"] == round((serie_kpi3["2026-03"] + serie_kpi3["2026-04"]) / 2, 4)


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


def test_kpi21_penetracion_reactivacion_se_calcula_con_reactivados_y_base_total():
    # KPI 21 = pacientes_reactivados / pacientes_inactivos_total, en %.
    # Con las dos variables presentes debe calcularse el valor esperado
    # (30 reactivados sobre una base inactiva total de 600 = 5.0%).
    variables = {
        "pacientes_reactivados": VariableValue(30, "wizard", 0.9),
        "pacientes_inactivos_total": VariableValue(600, "wizard", 0.9),
    }
    resultado = evaluar_cobertura(variables)
    assert 21 in resultado.kpis_calculados, "el KPI 21 debería estar calculado"
    assert resultado.kpis_calculados[21]["valor"] == round(100 * 30 / 600, 1)  # 5.0
    assert 21 not in resultado.kpis_parciales


def test_evaluar_cobertura_procesa_todo_kpi_formulas_sin_hardcodear_el_total():
    # Slice 2 podó KPI_FORMULAS de 21 a 16 entradas — evaluar_cobertura no
    # debe tener ningún "21"/"20" hardcodeado: itera `for kpi in
    # KPI_FORMULAS` (coverage.py), así que cada KPI del set actual cae en
    # exactamente uno de los buckets de CoverageResult, sin importar el
    # tamaño del set. Con variables vacías, todos quedan bloqueados,
    # esperando factura, o parciales — nunca calculados.
    resultado = evaluar_cobertura({})
    total_procesado = (
        len(resultado.kpis_calculados)
        + len(resultado.kpis_parciales)
        + len(resultado.kpis_bloqueados_por_diseno)
        + len(resultado.kpis_esperando_facturas)
        + len(resultado.kpis_esperando_resolucion_conflicto)
        + len(resultado.kpis_con_error)
    )
    assert total_procesado == len(KPI_FORMULAS) == 16, (
        f"evaluar_cobertura debería cubrir los {len(KPI_FORMULAS)} KPI_FORMULAS actuales, "
        f"cubrió {total_procesado}"
    )


def test_kpi21_queda_parcial_si_falta_la_base_inactiva_total():
    # Sin pacientes_inactivos_total (variable normal, va al wizard), el KPI
    # 21 no se calcula: queda pendiente esa única variable, no bloqueado ni
    # esperando facturas.
    variables = {
        "pacientes_reactivados": VariableValue(30, "wizard", 0.9),
    }
    resultado = evaluar_cobertura(variables)
    assert 21 not in resultado.kpis_calculados
    assert resultado.kpis_parciales[21] == ["pacientes_inactivos_total"]
    assert "pacientes_inactivos_total" in resultado.variables_pendientes


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
