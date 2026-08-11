"""
test_preguntas_wizard.py

Sin pytest: corre con `python -m parser.cobertura_calidad.test_preguntas_wizard`.
Cubre `preguntas_cubiertas_por_variables`: el cruce P# <-> variables de
`PREGUNTAS_WIZARD.referencia_guia` (uno-a-varios en ambos sentidos: una
variable puede listar varios P#, un mismo P# puede estar respaldado por
varias variables distintas).
"""

from parser.cobertura_calidad.preguntas_wizard import preguntas_cubiertas_por_variables


def test_pregunta_con_una_variable_faltante_queda_sin_cubrir():
    # P3 lo respaldan turnos_agendados/turnos_asistidos/no_shows/turnos_cancelados
    # (ver PREGUNTAS_WIZARD) — falta no_shows, así que sigue sin cubrirse.
    variables = {
        "turnos_agendados": 10,
        "turnos_asistidos": 8,
        "turnos_cancelados": 1,
    }
    cubiertas = preguntas_cubiertas_por_variables(variables)
    assert "P3" not in cubiertas


def test_pregunta_con_las_4_variables_presentes_queda_cubierta():
    variables = {
        "turnos_agendados": 10,
        "turnos_asistidos": 8,
        "no_shows": 1,
        "turnos_cancelados": 1,
    }
    cubiertas = preguntas_cubiertas_por_variables(variables)
    assert "P3" in cubiertas


def test_pregunta_sin_mapeo_en_wizard_nunca_aparece_cubierta():
    # P1 (contexto cualitativo) no tiene ninguna entrada en PREGUNTAS_WIZARD
    # que lo referencie -- nunca puede "cubrirse" por variables extraídas.
    variables = {
        "turnos_agendados": 10,
        "turnos_asistidos": 8,
        "no_shows": 1,
        "turnos_cancelados": 1,
    }
    cubiertas = preguntas_cubiertas_por_variables(variables)
    assert "P1" not in cubiertas


def test_referencia_con_multiples_ids_se_cubre_con_su_propia_variable():
    # "P8, P28" (horas_tarea_manual_semana) es una referencia multi-id de
    # UNA sola variable de wizard -- alcanza con esa variable sola.
    variables = {"horas_tarea_manual_semana": {"agenda": 5}}
    cubiertas = preguntas_cubiertas_por_variables(variables)
    assert {"P8", "P28"} <= cubiertas
    # "P33, P34" (tareas_sin_backup) es otra variable -- no se cubre porque
    # esa variable no está presente.
    assert "P33" not in cubiertas
    assert "P34" not in cubiertas


def test_sin_variables_no_cubre_ninguna_pregunta():
    assert preguntas_cubiertas_por_variables({}) == set()


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
