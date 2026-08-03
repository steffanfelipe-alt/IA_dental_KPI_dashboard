"""
test_trazabilidad.py

Sin pytest: corre con `python3 test_trazabilidad.py`.
Cubre la Fase 0 del plan de evolución (lineage): que un valor calculado se
pueda explicar ("390 min = 6.5 horas × 60, hoja Operativo, fila 3"), que la
ausencia de traza no rompa nada, y que la traza sobreviva al resto del
pipeline (conflictos, derivación).

Hallazgo #3 (E2E, fix de etiqueta): cuando `aplicar_mapeo` elige el ÚLTIMO
período de una serie como "valor vigente", la traza lo etiquetaba como "sum
de N registros" — mentira, ese valor es UNA sola celda (la del último
período), no la suma de las N filas que entraron a construir la serie
completa. El fix es solo de etiqueta: el valor numérico no cambia.
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


def test_valor_de_serie_se_explica_como_ultimo_periodo_no_como_suma_de_registros():
    # Hallazgo #3: la traza decía "sum de 4 registros" para un valor que en
    # realidad es SOLO la celda de Abril (102) — las otras 3 filas (Enero,
    # Febrero, Marzo) nunca se sumaron entre sí, solo sirvieron para armar
    # la serie histórica de la que se toma el último período.
    df = pd.DataFrame({
        "mes": ["Enero 2026", "Febrero 2026", "Marzo 2026", "Abril 2026"],
        "consultas": [95, 88, 110, 102],
    })
    mapeo = {
        "hoja": "Resumen", "fila_encabezado": 0,
        "orientacion": "periodos_en_filas", "columna_periodo": 0,
        "mapeo": [
            {"columna_index": 1, "variable": "consultas_nuevas_mes", "agregacion": "sum", "confianza": 0.9},
        ],
    }
    variables = aplicar_mapeo(df, mapeo)
    vv = variables["consultas_nuevas_mes"]

    # El fix es solo de etiqueta: el valor NO debe cambiar.
    assert vv.valor == 102, f"el valor no debe cambiar por el fix de traza, llegó {vv.valor}"
    assert vv.trazabilidad.n_registros == 1, (
        f"un valor de último período es UNA celda, no {vv.trazabilidad.n_registros} registros"
    )
    assert vv.trazabilidad.agregacion == "valor_vigente", (
        f"esperaba agregacion='valor_vigente', llegó {vv.trazabilidad.agregacion!r}"
    )

    texto = explicar(vv)
    assert "registros" not in texto, f"no debe mencionar 'registros' para un valor de último período: {texto}"
    assert "último período" in texto, f"debe decir 'último período': {texto}"
    assert "2026-04" in texto, f"debe citar el período vigente (2026-04): {texto}"


def test_valor_escalar_sin_serie_sigue_diciendo_suma_de_n_registros():
    # Regresión: una variable SIN columna de período (agregado escalar
    # normal) debe seguir explicándose como "sum de N registros" — el fix
    # de #3 es exclusivo de la rama de serie, no debe tocar este camino.
    df = pd.DataFrame({"no_show": [1, 0, 1, 1]})
    mapeo = {
        "hoja": None, "fila_encabezado": 0,
        "mapeo": [{"columna_index": 0, "variable": "no_shows", "agregacion": "sum", "confianza": 0.9}],
    }
    variables = aplicar_mapeo(df, mapeo)
    vv = variables["no_shows"]

    assert vv.valor == 3.0
    assert vv.trazabilidad.n_registros == 4, f"esperaba 4 registros (4 filas), llegó {vv.trazabilidad.n_registros}"
    assert vv.trazabilidad.agregacion == "sum"

    texto = explicar(vv)
    assert "sum de 4 registros" in texto, f"la rama sin serie debe seguir diciendo 'sum de N registros': {texto}"


def test_explicar_renderiza_valor_vigente_sin_periodo_disponible():
    # Caso borde de trazabilidad.explicar() en aislamiento: si algún día
    # llega agregacion="valor_vigente" sin vv.periodo seteado (no debería
    # pasar desde aplicar_mapeo, pero explicar() no debe romper), el texto
    # sigue diciendo "último período" sin intentar citar un período vacío.
    from types import SimpleNamespace

    t = Trazabilidad(
        origen="celda", hoja="Resumen", columna="consultas",
        agregacion="valor_vigente", n_registros=1, valor_final=102,
    )
    vv = SimpleNamespace(valor=102, fuente="migracion_excel", trazabilidad=t, periodo=None)
    texto = explicar(vv)
    assert "último período" in texto, f"debe decir 'último período' aun sin vv.periodo: {texto}"
    assert "registros" not in texto, f"no debe mencionar 'registros': {texto}"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
