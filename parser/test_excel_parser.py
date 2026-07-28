"""
test_excel_parser.py

Sin pytest (no está instalado en el entorno): corre con `python3 test_excel_parser.py`.
Cubre el bug de "AttributeError: 'float' object has no attribute 'values'":
aplicar_mapeo() no debe guardar un escalar para una variable tipo dict.
"""

import pandas as pd

from extractors.excel_parser import aplicar_mapeo


def _mapeo_hoja(mapeo: list[dict], hoja=None) -> dict:
    return {"hoja": hoja, "fila_encabezado": 0, "mapeo": mapeo}


def test_dict_con_columna_categoria_arma_desglose():
    df = pd.DataFrame({
        "tarea": ["Confirmar turnos", "Responder FAQ", "Confirmar turnos"],
        "horas": [5, 3, 4],
    })
    mapeo = _mapeo_hoja([
        {"columna_index": 1, "variable": "horas_tarea_manual_semana", "agregacion": "sum",
         "columna_categoria_index": 0, "confianza": 0.8},
    ])
    variables = aplicar_mapeo(df, mapeo)
    valor = variables["horas_tarea_manual_semana"].valor
    assert isinstance(valor, dict), f"esperaba dict, llegó {type(valor)}"
    assert valor == {"Confirmar turnos": 9.0, "Responder FAQ": 3.0}


def test_dict_sin_columna_categoria_no_rompe_arma_total():
    df = pd.DataFrame({"metrica": ["Horas tareas"], "horas": [21]})
    mapeo = _mapeo_hoja([
        {"columna_index": 1, "variable": "horas_tarea_manual_semana", "agregacion": "sum",
         "confianza": 0.8},
    ])
    variables = aplicar_mapeo(df, mapeo)
    valor = variables["horas_tarea_manual_semana"].valor
    assert isinstance(valor, dict), f"esperaba dict, llegó {type(valor)} (el bug original)"
    assert valor == {"total": 21.0}


def test_variable_escalar_sigue_funcionando_igual():
    df = pd.DataFrame({"no_show": [1, 0, 1, 1]})
    mapeo = _mapeo_hoja([
        {"columna_index": 0, "variable": "no_shows", "agregacion": "sum", "confianza": 0.9},
    ])
    variables = aplicar_mapeo(df, mapeo)
    assert variables["no_shows"].valor == 3.0
    assert isinstance(variables["no_shows"].valor, float)


def test_gana_mayor_confianza_para_variable_dict():
    df1 = pd.DataFrame({"tarea": ["Cargar datos"], "horas": [10]})
    df2 = pd.DataFrame({"tarea": ["Cargar datos"], "horas": [2]})
    variables = aplicar_mapeo(df1, _mapeo_hoja([
        {"columna_index": 1, "variable": "horas_tarea_manual_semana", "agregacion": "sum",
         "columna_categoria_index": 0, "confianza": 0.5},
    ], hoja="Hoja1"))
    variables = aplicar_mapeo(df2, _mapeo_hoja([
        {"columna_index": 1, "variable": "horas_tarea_manual_semana", "agregacion": "sum",
         "columna_categoria_index": 0, "confianza": 0.9},
    ], hoja="Hoja2"), variables)
    assert variables["horas_tarea_manual_semana"].valor == {"Cargar datos": 2.0}
    assert variables["horas_tarea_manual_semana"].fuente == "migracion_excel:Hoja2"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
