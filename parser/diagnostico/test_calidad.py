"""
test_calidad.py

Sin pytest: corre con `python -m parser.diagnostico.test_calidad`.
Cubre calidad.py (Fase 3, Data Quality Report): agregación pura sobre el
payload de pipeline.procesar_migracion, sin ninguna extracción nueva.
"""

from parser.diagnostico.calidad import evaluar_calidad, suficiencia_datos
from parser.cobertura_calidad.coverage import VariableValue
from parser.cobertura_calidad.reconciliacion import FUENTE_DERIVADA
from parser.vocabulario.schema import KPI_FORMULAS


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
    # "faltan", la completitud debería ser 100%, no menos — no tiene
    # sentido penalizar algo que nunca se le pide al dueño.
    kpis_calculados = {i: {} for i in range(1, 15)}  # 14 de los 16
    reporte = evaluar_calidad(_payload_base(
        kpis_calculados=kpis_calculados, kpis_bloqueados_por_diseno=[15, 16],
    ))
    assert reporte.completitud_pct == 100.0


def test_denominador_de_completitud_deriva_de_len_kpi_formulas_no_hardcodeado():
    # Coverage Denominator Consistency (spec kpi-vocabulario): con 3 KPIs
    # bloqueados por diseño, el denominador debe ser len(KPI_FORMULAS) - 3
    # = 16 - 3 = 13, nunca un "21"/"20" hardcodeado.
    kpis_calculados = {i: {} for i in range(1, 14)}  # 13 calculados
    reporte = evaluar_calidad(_payload_base(
        kpis_calculados=kpis_calculados, kpis_bloqueados_por_diseno=[100, 101, 102],
    ))
    kpis_relevantes_esperado = len(KPI_FORMULAS) - 3
    assert kpis_relevantes_esperado == 13, "len(KPI_FORMULAS) debería ser 16 tras la poda de Slice 2"
    assert reporte.completitud_pct == round(100 * 13 / kpis_relevantes_esperado, 1) == 100.0


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


# ---------------------------------------------------------------------------
# Fase D1: metodo = "medido" | "estimado" | "derivado", inferido automático
# en VariableValue.__post_init__ a partir de `fuente` — acá se prueba el
# efecto en suficiencia_datos, que es donde el plan dijo que debía pasar.
# ---------------------------------------------------------------------------

def test_suficiencia_datos_menor_con_variable_estimada_del_wizard():
    """Antes de Fase D1, "wizard" pesaba igual que "migracion_excel" acá
    (el único filtro era fuente != FUENTE_DERIVADA) — un dueño contestando
    de memoria contaba como si fuera tan sólido como una celda de Excel.
    Ya no: metodo="estimado" pesa 0.6, no 1.0."""
    variables_todas_medidas = {
        "turnos_agendados": VariableValue(73, "migracion_excel", 0.9),
        "no_shows": VariableValue(16, "migracion_excel", 0.9),
    }
    variables_con_estimada = {
        "turnos_agendados": VariableValue(73, "migracion_excel", 0.9),
        "no_shows": VariableValue(16, "wizard", 0.7),
    }
    suf_medidas = suficiencia_datos(4, variables_todas_medidas)  # KPI 4: tasa de no-show
    suf_estimada = suficiencia_datos(4, variables_con_estimada)
    assert suf_medidas == 1.0
    assert suf_estimada == 0.8, "(1.0 + 0.6) / 2 == 0.8"
    assert suf_estimada < suf_medidas


def test_suficiencia_datos_estimada_pesa_mas_que_derivada():
    """"estimado" (wizard, 0.6) sigue siendo más confiable que "derivado"
    (despejado algebraicamente, 0.0) — un dato que el dueño puso a mano,
    aunque sea de memoria, no es lo mismo que un número que nunca se leyó
    en ningún lado."""
    from parser.cobertura_calidad.reconciliacion import FUENTE_DERIVADA
    con_estimada = suficiencia_datos(4, {
        "turnos_agendados": VariableValue(73, "migracion_excel", 0.9),
        "no_shows": VariableValue(16, "wizard", 0.7),
    })
    con_derivada = suficiencia_datos(4, {
        "turnos_agendados": VariableValue(73, "migracion_excel", 0.9),
        "no_shows": VariableValue(16, FUENTE_DERIVADA, 0.6),
    })
    assert con_estimada > con_derivada


def test_metodo_se_infiere_solo_sin_tocar_ningun_call_site():
    """El campo existe y se infiere automático — ningún constructor de
    VariableValue en todo el código necesitó cambiar para esto."""
    from parser.cobertura_calidad.reconciliacion import FUENTE_DERIVADA
    assert VariableValue(1, "migracion_excel", 0.9).metodo == "medido"
    assert VariableValue(1, "migracion_excel:Resumen mensual", 0.9).metodo == "medido"
    assert VariableValue(1, "migracion_foto", 0.9).metodo == "medido"
    assert VariableValue(1, "sistema", 1.0).metodo == "medido"
    assert VariableValue(1, "confirmado_por_dueno", 1.0).metodo == "medido"
    assert VariableValue(1, "wizard", 0.7).metodo == "estimado"
    assert VariableValue(1, FUENTE_DERIVADA, 0.6).metodo == "derivado"


def test_metodo_explicito_no_se_pisa_con_la_inferencia():
    """Se puede forzar un metodo explícito si algún caso puntual lo
    necesita — la inferencia sólo corre cuando queda en None."""
    vv = VariableValue(1, "migracion_excel", 0.9, metodo="estimado")
    assert vv.metodo == "estimado"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
