"""
test_trazabilidad.py

Sin pytest: corre con `python3 test_trazabilidad.py`.
Cubre la Fase 0 del plan de evolución (lineage): que un valor calculado se
pueda explicar ("390 min = 6.5 horas × 60, hoja Operativo, fila 3"), que la
ausencia de traza no rompa nada, y que la traza sobreviva al resto del
pipeline (conflictos, derivación).
"""

import pandas as pd

from coverage import VariableValue
from conflictos import resolver_conflictos
from derivacion import derivar_variables_faltantes
from extractors.excel_parser import TasaDeclarada, aplicar_mapeo
from trazabilidad import Trazabilidad, explicar


def test_metricas_en_filas_explica_conversion_de_unidad():
    # El caso motivador del doc de deficiencias: 390 min no es un error de
    # cálculo (6.5 horas × 60 = 390 es correcto), lo que faltaba era poder
    # verlo. La hoja "Operativo" real es metricas_en_filas: cada fila es
    # una variable distinta con columnas Métrica/Valor.
    df = pd.DataFrame({
        "metrica": [
            "Horas/semana en tareas repetitivas",
            "% automatizado",
            "Tiempo de 1ra respuesta a consulta nueva",
        ],
        "valor": [21, 10, 6.5],
    })
    mapeo = {
        "hoja": "Operativo", "fila_encabezado": 0, "orientacion": "metricas_en_filas",
        "mapeo": [
            {"fila_index": 3, "columna_index": 1, "variable": "tiempo_respuesta_promedio_min",
             "unidad_origen": "horas", "confianza": 0.9},
        ],
    }
    variables = aplicar_mapeo(df, mapeo)
    vv = variables["tiempo_respuesta_promedio_min"]
    assert vv.valor == 390.0, f"esperaba 390.0, dio {vv.valor!r}"

    t = vv.trazabilidad
    assert t is not None, "la variable debería traer trazabilidad"
    assert t.origen == "celda"
    assert t.hoja == "Operativo"
    assert t.fila == 3
    assert t.valor_pre_conversion == 6.5
    assert t.unidad_origen == "horas"
    assert t.factor_conversion == 60

    texto = explicar(vv)
    for fragmento in ("390", "6.5", "60", "Operativo"):
        assert fragmento in texto, f"'{fragmento}' no aparece en la explicación: {texto!r}"


def test_filas_excluidas_quedan_en_la_traza():
    # Mismo fixture que test_excel_parser.py: una fila TOTAL no debe
    # tratarse como un período más, y eso debe quedar visible en la traza.
    df = pd.DataFrame({
        "mes": ["Enero 2026", "Febrero 2026", "Marzo 2026", "Abril 2026", "TOTAL"],
        "consultas": [95, 88, 110, 102, 395],
    })
    mapeo = {
        "hoja": "Resumen", "fila_encabezado": 0,
        "orientacion": "periodos_en_filas", "columna_periodo": 0,
        "filas_excluidas": [5],  # raw index de la fila TOTAL
        "mapeo": [
            {"columna_index": 1, "variable": "consultas_nuevas_mes", "agregacion": "sum", "confianza": 0.9},
        ],
    }
    variables = aplicar_mapeo(df, mapeo)
    t = variables["consultas_nuevas_mes"].trazabilidad
    assert t.filas_excluidas == [5], f"esperaba [5], dio {t.filas_excluidas!r}"

    texto = explicar(variables["consultas_nuevas_mes"])
    assert "excluidas 1 fila" in texto, f"la explicación no menciona la exclusión: {texto!r}"


def test_sin_traza_no_rompe_explicar():
    # Variables de wizard, sistema, o de un extractor que todavía no
    # popula trazabilidad (vision_parser) no deben romper la auditoría —
    # deben degradarse a un mensaje claro, no lanzar una excepción.
    vv = VariableValue(valor=42, fuente="wizard")
    assert vv.trazabilidad is None
    texto = explicar(vv)
    assert "42" in texto
    assert "sin traza registrada" in texto


def test_trazabilidad_sobrevive_a_resolver_conflictos():
    # Cuando no hay conflicto real (una fuente gana claramente por
    # confianza), el objeto VariableValue ganador pasa intacto — su
    # trazabilidad no debería perderse en el camino.
    traza = Trazabilidad(origen="celda", hoja="A", columna="consultas", valor_final=10)
    vv_alta = VariableValue(valor=10, fuente="migracion_excel:A", confianza=0.9, trazabilidad=traza)
    vv_baja = VariableValue(valor=99, fuente="migracion_excel:B", confianza=0.3)

    resueltas, conflictos = resolver_conflictos([
        {"consultas_nuevas_mes": vv_alta},
        {"consultas_nuevas_mes": vv_baja},
    ])

    assert not conflictos
    assert resueltas["consultas_nuevas_mes"].trazabilidad is traza


def test_trazabilidad_de_variable_derivada():
    # El otro tipo de procedencia: no_shows no viene de una celda, se
    # despeja de turnos_agendados × la tasa que la propia hoja declara.
    # Debe quedar igual de explicable que un valor extraído directo.
    variables = {
        "turnos_agendados": VariableValue(73, "migracion_excel", 0.9, archivo_origen="clinica.xlsx"),
    }
    tasas = {4: TasaDeclarada(vigente=21.9)}

    nuevas, _ = derivar_variables_faltantes(variables, tasas)
    vv = nuevas["no_shows"]
    assert vv.valor == 16.0

    t = vv.trazabilidad
    assert t is not None
    assert t.origen == "derivado_de_tasa"
    assert t.valor_pre_conversion == 73
    assert t.valor_final == 16.0

    texto = explicar(vv)
    assert "16" in texto and "73" in texto


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
