"""
test_validacion.py

Sin pytest: corre con `python3 test_validacion.py`.
Casos del plan de confiabilidad del agente de diagnóstico — cubre los
hallazgos A (fuga de variables internas) y B (guarda de tipos incompleta)
del informe de deficiencias, más las identidades entre variables.
"""

from validacion import validar_variable, validar_identidades, IDENTIDADES


def test_dict_valido_no_se_rechaza():
    assert validar_variable("horas_tarea_manual_semana", {"total": 21.0}, "migracion_excel") is None


def test_escalar_donde_va_dict_se_rechaza():
    motivo = validar_variable("horas_tarea_manual_semana", 21.0, "migracion_excel")
    assert motivo is not None and "dict" in motivo


def test_escalar_donde_va_list_se_rechaza():
    # hallazgo B: la guarda original de excel_parser.py solo cubría dict,
    # no list — tareas_sin_backup (list) con un float pasaba sin marca.
    motivo = validar_variable("tareas_sin_backup", 4.0, "migracion_excel")
    assert motivo is not None and "list" in motivo


def test_conteo_fraccionario_entre_0_y_1_se_rechaza():
    # el caso real: no_shows llegó como 0.2227 (la columna de TASA) en vez
    # del conteo de turnos ausentes.
    motivo = validar_variable("no_shows", 0.2227, "migracion_excel")
    assert motivo is not None and "conteo" in motivo


def test_conteo_entero_normal_no_se_rechaza():
    assert validar_variable("no_shows", 16, "migracion_excel") is None


def test_negativo_se_rechaza():
    assert validar_variable("monto_cobrado", -500, "migracion_excel") is not None


def test_variable_interna_desde_extractor_se_rechaza():
    # hallazgo A: nada impedía que un extractor escribiera
    # automatizaciones_activas — es una variable que solo debe calcular el
    # sistema.
    motivo = validar_variable("automatizaciones_activas", 5, "migracion_excel")
    assert motivo is not None and "interna" in motivo


def test_variable_interna_desde_sistema_no_se_rechaza():
    assert validar_variable("automatizaciones_activas", 5, "sistema") is None


def test_identidad_violada_se_detecta():
    violaciones = validar_identidades({"no_shows": 90, "turnos_agendados": 73})
    assert any(v.variable == "no_shows" for v in violaciones)


def test_identidad_dentro_de_tolerancia_no_se_marca():
    # 73*1.05 = 76.65 — 75 entra dentro del margen de desalineación de período
    violaciones = validar_identidades({"turnos_agendados": 75, "consultas_nuevas_mes": 73})
    assert violaciones == []


def test_identidad_sin_ambas_variables_no_rompe():
    assert validar_identidades({"no_shows": 16}) == []


def test_todas_las_identidades_referencian_variables_reales():
    from schema import VARIABLE_TYPES
    for menor, mayor in IDENTIDADES:
        assert menor in VARIABLE_TYPES, menor
        assert mayor in VARIABLE_TYPES, mayor


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
