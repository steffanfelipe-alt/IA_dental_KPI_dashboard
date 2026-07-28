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


def test_serie_periodo_excluye_fila_total_y_usa_ultimo_como_vigente():
    # hallazgo 1.1: una fila "TOTAL" después de los meses no debe
    # promediarse/sumarse como si fuera un período más.
    df = pd.DataFrame({
        "mes": ["Enero 2026", "Febrero 2026", "Marzo 2026", "Abril 2026", "TOTAL"],
        "consultas": [95, 88, 110, 102, 395],
    })
    mapeo = {
        "hoja": "Resumen", "fila_encabezado": 0,
        "orientacion": "periodos_en_filas", "columna_periodo": 0,
        "filas_excluidas": [5],  # raw index de la fila TOTAL (post-header idx 4 + fila_encabezado 0 + 1)
        "mapeo": [
            {"columna_index": 1, "variable": "consultas_nuevas_mes", "agregacion": "sum", "confianza": 0.9},
        ],
    }
    variables = aplicar_mapeo(df, mapeo)
    vv = variables["consultas_nuevas_mes"]
    assert vv.valor == 102, f"esperaba el último mes real (102), no algo inflado por TOTAL: {vv.valor}"
    # Fase 1: la serie usa clave canónica ("2026-04"), no la etiqueta cruda
    # de la hoja — es lo que permite que dos archivos con etiquetas
    # distintas del mismo mes intersecten en coverage._calcular_serie_kpi.
    assert vv.serie == {"2026-01": 95.0, "2026-02": 88.0, "2026-03": 110.0, "2026-04": 102.0}
    assert vv.periodo == "2026-04"
    # La etiqueta cruda no se pierde, queda disponible para mostrar.
    assert vv.etiquetas_originales == {
        "2026-01": "Enero 2026", "2026-02": "Febrero 2026",
        "2026-03": "Marzo 2026", "2026-04": "Abril 2026",
    }


def test_serie_normaliza_etiquetas_de_archivos_distintos_al_mismo_mes():
    # El hueco real que motivó la Fase 1: un archivo etiqueta el mes
    # "Abril 2026" y otro "2026-04" — sin normalizar, estas dos series NO
    # intersectarían nunca en coverage._calcular_serie_kpi.
    df_texto = pd.DataFrame({"mes": ["Marzo 2026", "Abril 2026"], "turnos": [79, 73]})
    mapeo_texto = {
        "hoja": "ConsultorioA", "fila_encabezado": 0,
        "orientacion": "periodos_en_filas", "columna_periodo": 0,
        "mapeo": [{"columna_index": 1, "variable": "turnos_agendados", "agregacion": "sum", "confianza": 0.9}],
    }
    df_iso = pd.DataFrame({"periodo": ["2026-03", "2026-04"], "no_shows": [12, 16]})
    mapeo_iso = {
        "hoja": "ConsultorioB", "fila_encabezado": 0,
        "orientacion": "periodos_en_filas", "columna_periodo": 0,
        "mapeo": [{"columna_index": 1, "variable": "no_shows", "agregacion": "sum", "confianza": 0.9}],
    }
    variables = aplicar_mapeo(df_texto, mapeo_texto)
    variables = aplicar_mapeo(df_iso, mapeo_iso, variables)

    assert set(variables["turnos_agendados"].serie) == {"2026-03", "2026-04"}
    assert set(variables["no_shows"].serie) == {"2026-03", "2026-04"}


def test_metricas_en_filas_no_mezcla_metricas_distintas():
    # hallazgo 1.3: una hoja "una fila = una métrica" no debe promediar
    # columnas de métricas sin relación entre sí.
    df = pd.DataFrame({
        "metrica": ["Tiempo de 1ra respuesta", "Horas tareas manuales", "% automatizado"],
        "valor": [6.5, 21, 0.05],
    })
    mapeo = {
        "hoja": "Operativo", "fila_encabezado": 0, "orientacion": "metricas_en_filas",
        "mapeo": [
            {"fila_index": 1, "columna_index": 1, "variable": "tiempo_respuesta_promedio_min",
             "unidad_origen": "horas", "confianza": 0.85},
            {"fila_index": 2, "columna_index": 1, "variable": "horas_tarea_manual_semana",
             "unidad_origen": "horas", "confianza": 0.8},
        ],
    }
    variables = aplicar_mapeo(df, mapeo)
    # 6.5 horas -> 390 min, y NO se mezcla con las otras dos filas
    assert variables["tiempo_respuesta_promedio_min"].valor == 390.0
    assert variables["horas_tarea_manual_semana"].valor == {"total": 21.0}


def test_conversion_horas_a_minutos():
    df = pd.DataFrame({"valor": [6.5]})
    mapeo = _mapeo_hoja([
        {"columna_index": 0, "variable": "tiempo_respuesta_promedio_min", "agregacion": "avg",
         "unidad_origen": "horas", "confianza": 0.9},
    ])
    variables = aplicar_mapeo(df, mapeo)
    assert variables["tiempo_respuesta_promedio_min"].valor == 390.0


def test_columna_periodo_como_nombre_de_texto_no_rompe():
    # visto en la práctica: Claude devolvió "columna_periodo": "Mes" (el
    # nombre) en vez de 0 (el índice) pese a la instrucción del prompt —
    # no debe tirar TypeError, debe degradar a "sin serie" con gracia.
    df = pd.DataFrame({"mes": ["Enero 2026", "Febrero 2026"], "valor": [10, 20]})
    mapeo = {
        "hoja": "X", "fila_encabezado": 0, "orientacion": "periodos_en_filas",
        "columna_periodo": "Mes", "filas_excluidas": [],
        "mapeo": [{"columna_index": 1, "variable": "consultas_nuevas_mes", "agregacion": "sum", "confianza": 0.9}],
    }
    variables = aplicar_mapeo(df, mapeo)
    assert variables["consultas_nuevas_mes"].valor == 30.0
    assert variables["consultas_nuevas_mes"].serie is None


def test_variable_tipo_list_nunca_se_mapea_desde_excel():
    # hallazgo B: tareas_sin_backup es tipo "list" — excel_parser no
    # produce listas, así que ni siquiera debe intentar mapearla.
    df = pd.DataFrame({"valor": [4]})
    mapeo = _mapeo_hoja([
        {"columna_index": 0, "variable": "tareas_sin_backup", "agregacion": "sum", "confianza": 0.9},
    ])
    variables = aplicar_mapeo(df, mapeo)
    assert "tareas_sin_backup" not in variables


def test_columna_con_formato_porcentaje_no_puede_mapear_a_un_conteo():
    # Inyección de error: se fuerza el mapeo de la columna de TASA a
    # no_shows (un conteo) — exactamente el bug que originó el plan. La
    # guarda de formato debe rechazarlo sin depender del modelo.
    df = pd.DataFrame({"mes": ["Abril 2026"], "tasa_no_show": [0.219]})
    mapeo = _mapeo_hoja([
        {"columna_index": 1, "variable": "no_shows", "agregacion": "sum", "confianza": 0.9},
    ])
    variables = aplicar_mapeo(df, mapeo, formatos_columna={1: "porcentaje"})
    assert "no_shows" not in variables


def test_sin_formatos_la_guarda_no_bloquea_nada():
    # Un CSV no tiene metadata de formato: todo debe seguir funcionando.
    df = pd.DataFrame({"mes": ["Abril 2026"], "ausencias": [16]})
    mapeo = _mapeo_hoja([
        {"columna_index": 1, "variable": "no_shows", "agregacion": "sum", "confianza": 0.9},
    ])
    assert aplicar_mapeo(df, mapeo)["no_shows"].valor == 16.0


def test_formato_moneda_no_bloquea_un_monto():
    df = pd.DataFrame({"mes": ["Abril 2026"], "cobrado": [5320000]})
    mapeo = _mapeo_hoja([
        {"columna_index": 1, "variable": "monto_cobrado", "agregacion": "sum", "confianza": 0.9},
    ])
    variables = aplicar_mapeo(df, mapeo, formatos_columna={1: "moneda"})
    assert variables["monto_cobrado"].valor == 5320000.0


def test_clasificar_formato_reconoce_los_casos_reales():
    from extractors.excel_parser import _clasificar_formato
    assert _clasificar_formato("0.0%") == "porcentaje"
    assert _clasificar_formato('"$"#,##0') == "moneda"
    assert _clasificar_formato("General") == "general"
    assert _clasificar_formato("dd/mm/yyyy") == "fecha"
    assert _clasificar_formato("") == "general"


def test_leer_formatos_del_fixture_real():
    # El fixture se genera con formatos realistas (ver generar_fixtures.py):
    # las 4 columnas de tasa deben salir como porcentaje.
    import os
    from extractors.excel_parser import leer_formatos_columna
    path = os.path.join(os.path.dirname(__file__), "evals", "fixtures", "clinica_demo_metricas.xlsx")
    if not os.path.exists(path):
        return  # el fixture se regenera con evals/generar_fixtures.py
    formatos = leer_formatos_columna(path)
    resumen = formatos["Resumen mensual"]
    assert [resumen[i] for i in (7, 8, 9, 10)] == ["porcentaje"] * 4
    assert resumen[1] == "general"  # la columna de conteo NO es porcentaje


def test_leer_formatos_de_csv_devuelve_vacio():
    from extractors.excel_parser import leer_formatos_columna
    assert leer_formatos_columna("cualquier_cosa.csv") == {}


def test_ingreso_por_paciente_fusiona_variantes_del_mismo_nombre_via_matching():
    # El bug real del doc de deficiencias (punto 3): sin matching, "Juan
    # Perez" y "J. Perez" quedan como dos claves del dict y KPI 14 (LTV)
    # se subestima en silencio.
    from matching import RegistroClientes

    df = pd.DataFrame({
        "paciente": ["Juan Perez", "J. Perez", "Juan Perez"],
        "monto": [50000, 30000, 20000],
    })
    mapeo = _mapeo_hoja([
        {"columna_index": 1, "variable": "ingreso_por_paciente", "agregacion": "sum",
         "columna_categoria_index": 0, "confianza": 0.9},
    ])
    variables = aplicar_mapeo(df, mapeo, registro_clientes=RegistroClientes())
    valor = variables["ingreso_por_paciente"].valor
    assert len(valor) == 1, f"las 3 filas deberían resolver a un solo paciente, dio {valor!r}"
    assert list(valor.values())[0] == 100000.0


def test_sin_registro_clientes_ingreso_por_paciente_se_comporta_como_antes():
    # Nadie pasa registro_clientes (default None): mismo comportamiento
    # de siempre, categoría cruda tal cual — sin romper compatibilidad.
    df = pd.DataFrame({"paciente": ["Juan Perez", "J. Perez"], "monto": [50000, 30000]})
    mapeo = _mapeo_hoja([
        {"columna_index": 1, "variable": "ingreso_por_paciente", "agregacion": "sum",
         "columna_categoria_index": 0, "confianza": 0.9},
    ])
    variables = aplicar_mapeo(df, mapeo)
    assert len(variables["ingreso_por_paciente"].valor) == 2


def test_ingreso_por_tratamiento_nunca_pasa_por_matching_de_pacientes():
    # Guarda crítica (schema.MetricaInfo.entidad): ingreso_por_tratamiento
    # comparte _agregar_dict con ingreso_por_paciente, pero su entidad es
    # "tratamiento" — no debe fusionar tratamientos como si fueran
    # pacientes aunque se pase un registro_clientes.
    from matching import RegistroClientes

    df = pd.DataFrame({"tratamiento": ["Ortodoncia", "Ortodoncia (plan completo)"], "monto": [1000, 2000]})
    mapeo = _mapeo_hoja([
        {"columna_index": 1, "variable": "ingreso_por_tratamiento", "agregacion": "sum",
         "columna_categoria_index": 0, "confianza": 0.9},
    ])
    variables = aplicar_mapeo(df, mapeo, registro_clientes=RegistroClientes())
    assert len(variables["ingreso_por_tratamiento"].valor) == 2


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
