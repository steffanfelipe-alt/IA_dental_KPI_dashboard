"""
test_agregados.py

Sin pytest: corre con `python3 test_agregados.py`.
Cubre la Fase 1 del plan de evolución: calcular_agregado (punto 1 del doc
de deficiencias — el promedio se calcula en Python sobre la serie ya
extraída, nunca se le pide al LLM que lo resuma) y detectar_outliers.

Cruza los agregados contra los valores dorados de evals/casos_dorados.py:
esos números ya están verificados a mano contra el fixture real, así que
sirven de golden gratis para `calcular_agregado` sin escribir un fixture
nuevo.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "evals"))

from agregados import calcular_agregado, detectar_outliers  # noqa: E402
import casos_dorados as dorado  # noqa: E402
from generar_fixtures import CONSULTAS_NUEVAS, MESES  # noqa: E402


def test_promedio_reproduce_el_promedio_dorado_de_4_meses():
    serie = dict(zip(MESES, CONSULTAS_NUEVAS))
    promedio = calcular_agregado(serie, "promedio")
    assert promedio == round(dorado.PROMEDIO_4_MESES["consultas_nuevas_mes"], 4)


def test_promedio_no_cae_en_el_bug_de_la_fila_total():
    # Sin la fila TOTAL (que el pipeline ya excluye antes de llegar acá):
    # el promedio real NO debe coincidir con lo que daría si esa fila se
    # colara como si fuera un quinto mes (hallazgo 1.1).
    serie_real = dict(zip(MESES, CONSULTAS_NUEVAS))
    promedio_real = calcular_agregado(serie_real, "promedio")

    serie_con_bug = dict(serie_real)
    serie_con_bug["TOTAL"] = sum(CONSULTAS_NUEVAS)
    promedio_con_bug = calcular_agregado(serie_con_bug, "promedio")

    assert promedio_real == round(dorado.PROMEDIO_4_MESES["consultas_nuevas_mes"], 4)
    assert promedio_con_bug == round(dorado.PROMEDIO_CON_BUG_TOTAL["consultas_nuevas_mes"], 4)
    assert promedio_real != promedio_con_bug


def test_mediana_de_serie_impar():
    serie = {"2026-01": 10, "2026-02": 20, "2026-03": 30}
    assert calcular_agregado(serie, "mediana") == 20


def test_mediana_de_serie_par_promedia_los_dos_centrales():
    serie = {"2026-01": 10, "2026-02": 20, "2026-03": 30, "2026-04": 40}
    assert calcular_agregado(serie, "mediana") == 25


def test_suma_y_ultimo():
    serie = {"2026-01": 10, "2026-02": 20, "2026-03": 30}
    assert calcular_agregado(serie, "suma") == 60
    assert calcular_agregado(serie, "ultimo") == 30  # confía en el orden del dict


def test_ultimo_saltea_none_al_final_de_la_serie():
    # Bug real encontrado probando con datos reales: un KPI porcentual
    # (_pct) devuelve None para un período cuyo denominador dio 0 (ej. un
    # mes sin turnos agendados). Si ese período es el más reciente,
    # "ultimo" no debe explotar — tiene que saltear al último numérico.
    serie = {"2026-01": 10, "2026-02": 20, "2026-03": None}
    assert calcular_agregado(serie, "ultimo") == 20


def test_agregado_ignora_valores_no_numericos_sin_romper():
    # KPIs 19/20: el valor por período es un dict, no un escalar.
    serie = {"2026-01": {"a": 1}, "2026-02": {"a": 2}}
    assert calcular_agregado(serie, "promedio") is None


def test_serie_vacia_da_none():
    assert calcular_agregado({}, "promedio") is None


def test_metodo_desconocido_rompe_explicito():
    try:
        calcular_agregado({"2026-01": 1}, "moda")
        assert False, "debería haber lanzado ValueError"
    except ValueError:
        pass


def test_outlier_10x_se_detecta_sin_alterar_el_agregado():
    serie = {"2026-01": 100, "2026-02": 105, "2026-03": 1050, "2026-04": 98}
    sospechosos = detectar_outliers(serie, factor=10)
    assert sospechosos == ["2026-03"], f"esperaba solo 2026-03, dio {sospechosos!r}"

    # El agregado no descarta el outlier — sigue siendo el promedio de
    # TODOS los valores, el outlier queda visible pero no se esconde nada.
    promedio_con_outlier = calcular_agregado(serie, "promedio")
    assert promedio_con_outlier == round((100 + 105 + 1050 + 98) / 4, 4)


def test_sin_outliers_no_reporta_nada():
    serie = {"2026-01": 100, "2026-02": 105, "2026-03": 98, "2026-04": 102}
    assert detectar_outliers(serie, factor=10) == []


def test_serie_de_un_solo_valor_no_tiene_con_que_comparar():
    assert detectar_outliers({"2026-01": 100}) == []


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
