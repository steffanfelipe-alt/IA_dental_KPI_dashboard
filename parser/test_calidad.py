"""
test_calidad.py

Sin pytest: corre con `python3 test_calidad.py`.
Cubre calidad.py (Fase 3, Data Quality Report): agregación pura sobre el
payload de pipeline.procesar_migracion, sin ninguna extracción nueva.
"""

from calidad import evaluar_calidad, suficiencia_datos
from coverage import VariableValue
from reconciliacion import FUENTE_DERIVADA


def _payload_base(**overrides):
    base = {
        "kpis_calculados": {}, "kpis_bloqueados_por_diseno": [], "kpis_con_error": {},
        "kpis_esperando_resolucion_conflicto": {}, "variables_en_cuarentena": {},
        "discrepancias_reconciliacion": [], "variables": {},
    }
    base.update(overrides)
    return base


def test_sin_archivos_completitud_es_cero_sin_division_por_cero():
    payload = _payload_base()
    reporte = evaluar_calidad(payload)
    assert reporte.completitud_pct == 0.0
    assert reporte.consistencia_pct == 100.0  # nada intentado, nada inconsistente
    assert reporte.confianza_promedio is None
    assert reporte.datos_en_cuarentena == 0
    assert reporte.kpis_afectados == []


def test_cuarentena_no_vacia_baja_la_consistencia():
    limpio = evaluar_calidad(_payload_base(
        variables={"turnos_agendados": VariableValue(70, "migracion_excel", 0.9)},
    ))
    con_cuarentena = evaluar_calidad(_payload_base(
        variables={"turnos_agendados": VariableValue(70, "migracion_excel", 0.9)},
        variables_en_cuarentena={"no_shows": {"valor": 0.22, "fuente": "migracion_excel", "motivo": "fracción, no conteo"}},
    ))
    assert con_cuarentena.consistencia_pct < limpio.consistencia_pct
    assert con_cuarentena.datos_en_cuarentena == 1


def test_completitud_excluye_kpis_bloqueados_por_diseno():
    # Si los únicos 2 KPIs bloqueados por diseño son los únicos que
    # "faltan", la completitud debería ser 100%, no 90% — no tiene sentido
    # penalizar algo que nunca se le pide al dueño.
    kpis_calculados = {i: {} for i in range(1, 19)}  # 18 de los 20
    reporte = evaluar_calidad(_payload_base(
        kpis_calculados=kpis_calculados, kpis_bloqueados_por_diseno=[16, 17],
    ))
    assert reporte.completitud_pct == 100.0


def test_kpis_afectados_incluye_error_conflicto_y_cuarentena():
    reporte = evaluar_calidad(_payload_base(
        kpis_con_error={5: "ZeroDivisionError"},
        kpis_esperando_resolucion_conflicto={9: ["pacientes_reactivados"]},
        variables_en_cuarentena={"no_shows": {"valor": 0.22, "fuente": "x", "motivo": "y"}},
    ))
    # no_shows es variable del KPI 4 (tasa de no-show)
    assert reporte.kpis_afectados == [4, 5, 9]


def test_confianza_promedio_de_las_variables_aceptadas():
    reporte = evaluar_calidad(_payload_base(variables={
        "a": VariableValue(1, "migracion_excel", 0.8),
        "b": VariableValue(2, "migracion_excel", 0.6),
    }))
    assert reporte.confianza_promedio == 70.0


def test_suficiencia_datos_menor_con_variable_derivada():
    variables_todas_observadas = {
        "turnos_agendados": VariableValue(73, "migracion_excel", 0.9),
        "no_shows": VariableValue(16, "migracion_excel", 0.9),
    }
    variables_con_derivada = {
        "turnos_agendados": VariableValue(73, "migracion_excel", 0.9),
        "no_shows": VariableValue(16, FUENTE_DERIVADA, 0.6),
    }
    suf_observadas = suficiencia_datos(4, variables_todas_observadas)  # KPI 4: tasa de no-show
    suf_derivada = suficiencia_datos(4, variables_con_derivada)
    assert suf_observadas == 1.0
    assert suf_derivada == 0.5
    assert suf_derivada < suf_observadas


def test_suficiencia_datos_none_si_no_calculable():
    assert suficiencia_datos(4, {"turnos_agendados": VariableValue(73, "migracion_excel", 0.9)}) is None


def test_suficiencia_datos_kpi_inexistente_no_rompe():
    assert suficiencia_datos(999, {}) is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
