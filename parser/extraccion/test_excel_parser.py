"""
test_excel_parser.py

Sin pytest (no está instalado en el entorno): corre con `python -m parser.extraccion.test_excel_parser`.
Cubre el bug de "AttributeError: 'float' object has no attribute 'values'":
aplicar_mapeo() no debe guardar un escalar para una variable tipo dict.
"""

import json
import tempfile
from pathlib import Path

import pandas as pd

from parser.extraccion.excel_parser import aplicar_mapeo, parsear_excel, _armar_registros_ledger, _fusionar_ledger


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
    from parser.extraccion.excel_parser import _clasificar_formato
    assert _clasificar_formato("0.0%") == "porcentaje"
    assert _clasificar_formato('"$"#,##0') == "moneda"
    assert _clasificar_formato("General") == "general"
    assert _clasificar_formato("dd/mm/yyyy") == "fecha"
    assert _clasificar_formato("") == "general"


def test_leer_formatos_del_fixture_real():
    # El fixture se genera con formatos realistas (ver generar_fixtures.py):
    # las 4 columnas de tasa deben salir como porcentaje.
    import os
    from parser.extraccion.excel_parser import leer_formatos_columna
    path = os.path.join(os.path.dirname(__file__), "evals", "fixtures", "clinica_demo_metricas.xlsx")
    if not os.path.exists(path):
        return  # el fixture se regenera con evals/generar_fixtures.py
    formatos = leer_formatos_columna(path)
    resumen = formatos["Resumen mensual"]
    assert [resumen[i] for i in (7, 8, 9, 10)] == ["porcentaje"] * 4
    assert resumen[1] == "general"  # la columna de conteo NO es porcentaje


def test_leer_formatos_de_csv_devuelve_vacio():
    from parser.extraccion.excel_parser import leer_formatos_columna
    assert leer_formatos_columna("cualquier_cosa.csv") == {}


def test_ingreso_por_paciente_fusiona_variantes_del_mismo_nombre_via_matching():
    # El bug real del doc de deficiencias (punto 3): sin matching, "Juan
    # Perez" y "J. Perez" quedan como dos claves del dict y el LTV real
    # (ltv_real()) se subestima en silencio.
    from parser.pacientes.matching import RegistroClientes

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
    from parser.pacientes.matching import RegistroClientes

    df = pd.DataFrame({"tratamiento": ["Ortodoncia", "Ortodoncia (plan completo)"], "monto": [1000, 2000]})
    mapeo = _mapeo_hoja([
        {"columna_index": 1, "variable": "ingreso_por_tratamiento", "agregacion": "sum",
         "columna_categoria_index": 0, "confianza": 0.9},
    ])
    variables = aplicar_mapeo(df, mapeo, registro_clientes=RegistroClientes())
    assert len(variables["ingreso_por_tratamiento"].valor) == 2


# ---------------------------------------------------------------------------
# Regresión: filas que no son un período no pueden ser el valor vigente.
# Bug real (planilla "clinica_sonrisas"): la nota al pie de la hoja Financiero
# entraba a la serie como período, quedaba última al ordenar (ASCII pone 'P'
# después de '2') y se elegía como vigente -> throughput = 0.
# ---------------------------------------------------------------------------

def _mapeo_con_periodo(mapeo: list[dict]) -> dict:
    return {"hoja": None, "fila_encabezado": 0, "orientacion": "periodos_en_filas",
            "columna_periodo": 0, "mapeo": mapeo}


def test_nota_al_pie_sin_dato_no_se_cuela_como_periodo_con_valor_cero():
    """Guarda 1 (min_count): un grupo enteramente NaN debe dar NaN, no 0.0."""
    df = pd.DataFrame({
        "mes": ["Enero 2026", "Febrero 2026", "Cobro = cobrado / facturado."],
        "cobrado": [4460000, 4200000, None],
    })
    vv = aplicar_mapeo(df, _mapeo_con_periodo([
        {"columna_index": 1, "variable": "monto_cobrado", "agregacion": "sum", "confianza": 0.9},
    ]))["monto_cobrado"]

    assert vv.valor == 4200000.0, "el vigente debe ser el último mes real, no la nota al pie"
    assert vv.periodo == "2026-02"
    assert list(vv.serie) == ["2026-01", "2026-02"], "la nota no debe existir como período"


def test_fila_total_con_dato_real_no_entra_a_la_serie_pero_queda_visible():
    """Guarda 2 (es_canonico): cubre el caso que min_count no puede — una fila
    basura CON número, típicamente un TOTAL que el modelo no listó en
    filas_excluidas."""
    df = pd.DataFrame({
        "mes": ["Enero 2026", "Febrero 2026", "TOTAL / Prom."],
        "consultas": [95, 88, 183],
    })
    vv = aplicar_mapeo(df, _mapeo_con_periodo([
        {"columna_index": 1, "variable": "consultas_nuevas_mes", "agregacion": "sum", "confianza": 0.9},
    ]))["consultas_nuevas_mes"]

    assert vv.valor == 88.0, "el TOTAL nunca puede ser el valor vigente"
    assert "TOTAL / Prom." not in (vv.serie or {})
    assert vv.periodos_no_reconocidos == {"TOTAL / Prom.": 183.0}, "no desaparece en silencio"


def test_serie_sin_ningun_periodo_canonico_cae_al_agregado_escalar():
    """Una hoja rotulada 'Semana 1..3' no tiene claves canónicas: la serie
    queda vacía y se cae al escalar, igual que cuando no hay columna de
    período. No se inventa un período ni se elige una etiqueta arbitraria."""
    df = pd.DataFrame({
        "periodo": ["Semana 1", "Semana 2", "Semana 3"],
        "consultas": [20, 25, 30],
    })
    vv = aplicar_mapeo(df, _mapeo_con_periodo([
        {"columna_index": 1, "variable": "consultas_nuevas_mes", "agregacion": "sum", "confianza": 0.9},
    ]))["consultas_nuevas_mes"]

    assert vv.serie is None
    assert vv.valor == 75.0
    assert len(vv.periodos_no_reconocidos) == 3


def test_hoja_limpia_no_reporta_periodos_no_reconocidos():
    df = pd.DataFrame({"mes": ["Enero 2026", "Febrero 2026"], "consultas": [95, 88]})
    vv = aplicar_mapeo(df, _mapeo_con_periodo([
        {"columna_index": 1, "variable": "consultas_nuevas_mes", "agregacion": "sum", "confianza": 0.9},
    ]))["consultas_nuevas_mes"]

    assert vv.periodos_no_reconocidos is None
    assert vv.valor == 88.0


# ---------------------------------------------------------------------------
# Fase 0.1: binning mensual. Bug real (presupuestos_marzo2026.csv): una hoja
# transaccional con una fecha real por fila agrupaba por la etiqueta CRUDA
# (cada día es su propio grupo) y recién después normalizaba a mes — al
# colisionar en la misma clave, la última fila pisaba a las anteriores. La
# suma de los aceptados de marzo daba 787.000 (el monto del 2026-03-25) en
# vez de 8.989.000 (la suma real de las 29 filas del mes).
# ---------------------------------------------------------------------------

def _mapeo_transaccional(mapeo: list[dict]) -> dict:
    return {"hoja": None, "fila_encabezado": 0, "orientacion": "transaccional",
            "columna_periodo": 0, "mapeo": mapeo}


def test_varias_fechas_del_mismo_mes_suman_el_mes_no_el_ultimo_dia():
    df = pd.DataFrame({
        "fecha": ["2026-03-01", "2026-03-05", "2026-03-28", "2026-04-02"],
        "monto": [100000, 200000, 300000, 50000],
    })
    vv = aplicar_mapeo(df, _mapeo_transaccional([
        {"columna_index": 1, "variable": "monto_presupuestos_aceptados", "agregacion": "sum", "confianza": 0.9},
    ]))["monto_presupuestos_aceptados"]

    assert vv.serie == {"2026-03": 600000.0, "2026-04": 50000.0}, (
        "marzo debe sumar las tres filas (600.000), no quedarse con la del "
        "último día (300.000) — ese era exactamente el bug"
    )
    assert vv.valor == 50000.0, "vigente = último período real, sin tocar (Fase A)"
    assert vv.etiquetas_originales["2026-03"] == "2026-03-01", (
        "con varias fechas en el mismo mes, la etiqueta representativa es la más temprana"
    )


def test_varias_fechas_del_mismo_mes_con_avg_promedia_el_mes():
    df = pd.DataFrame({
        "fecha": ["2026-03-01", "2026-03-10", "2026-03-20"],
        "duracion_min": [100, 200, 300],
    })
    vv = aplicar_mapeo(df, _mapeo_transaccional([
        {"columna_index": 1, "variable": "tiempo_respuesta_promedio_min", "agregacion": "avg", "confianza": 0.9},
    ]))["tiempo_respuesta_promedio_min"]

    assert vv.serie == {"2026-03": 200.0}, "avg debe promediar el mes (200), no quedarse con el último (300)"


def test_periodos_en_filas_sin_regresion_una_etiqueta_por_mes():
    """No-regresión: la hoja típica (un mes, una fila) debe seguir dando
    exactamente lo mismo que antes de normalizar-antes-de-agrupar."""
    df = pd.DataFrame({
        "mes": ["Enero 2026", "Febrero 2026", "Marzo 2026"],
        "cobrado": [4460000, 4200000, 5940000],
    })
    vv = aplicar_mapeo(df, _mapeo_con_periodo([
        {"columna_index": 1, "variable": "monto_cobrado", "agregacion": "sum", "confianza": 0.9},
    ]))["monto_cobrado"]

    assert vv.serie == {"2026-01": 4460000.0, "2026-02": 4200000.0, "2026-03": 5940000.0}
    assert vv.valor == 5940000.0
    assert vv.etiquetas_originales == {"2026-01": "Enero 2026", "2026-02": "Febrero 2026", "2026-03": "Marzo 2026"}


# ---------------------------------------------------------------------------
# Fase H6: "condicion" — nunca cubierto por un test hasta ahora
# ---------------------------------------------------------------------------

def test_condicion_valida_filtra_las_filas():
    df = pd.DataFrame({"estado": ["aceptado", "pendiente", "aceptado"], "monto": [100, 50, 200]})
    vv = aplicar_mapeo(df, _mapeo_hoja([
        {"columna_index": 1, "variable": "monto_presupuestos_aceptados", "agregacion": "sum",
         "condicion": "estado == 'aceptado'", "confianza": 0.9},
    ]))["monto_presupuestos_aceptados"]
    assert vv.valor == 300.0  # 100 + 200, nunca los 350 sin filtrar


def test_condicion_que_pandas_no_puede_parsear_descarta_la_regla_no_ejecuta_sin_filtrar():
    df = pd.DataFrame({"Estado turno": ["aceptado", "pendiente"], "monto": [100, 50]})
    # la condición referencia "estado" pero la columna real es "Estado turno"
    # (con espacio, sin backticks) -> pandas.query no puede resolverla
    variables = aplicar_mapeo(df, _mapeo_hoja([
        {"columna_index": 1, "variable": "monto_presupuestos_aceptados", "agregacion": "sum",
         "condicion": "estado == 'aceptado'", "confianza": 0.9},
    ]))
    assert "monto_presupuestos_aceptados" not in variables  # nunca 150 (sin filtrar)


def test_agregacion_count_where_cuenta_filas_tras_filtrar():
    df = pd.DataFrame({"estado": ["no show", "asistio", "no show", "asistio"]})
    vv = aplicar_mapeo(df, _mapeo_hoja([
        {"columna_index": 0, "variable": "no_shows", "agregacion": "count_where",
         "condicion": "estado == 'no show'", "confianza": 0.9},
    ]))["no_shows"]
    assert vv.valor == 2.0


# ---------------------------------------------------------------------------
# Fase H5: "hoja_estimada" — metodo="estimado" para toda la hoja
# ---------------------------------------------------------------------------

def test_hoja_estimada_pasa_metodo_estimado_a_sus_variables():
    df = pd.DataFrame({"tiempo_respuesta_promedio_min": [12]})
    mapeo = {
        "hoja": "Operativo", "fila_encabezado": 0, "hoja_estimada": True,
        "mapeo": [{"columna_index": 0, "variable": "tiempo_respuesta_promedio_min", "agregacion": "sum", "confianza": 0.8}],
    }
    vv = aplicar_mapeo(df, mapeo)["tiempo_respuesta_promedio_min"]
    assert vv.metodo == "estimado"


def test_sin_hoja_estimada_se_sigue_infiriendo_como_antes():
    df = pd.DataFrame({"no_shows": [1, 0, 1]})
    vv = aplicar_mapeo(df, _mapeo_hoja([
        {"columna_index": 0, "variable": "no_shows", "agregacion": "sum", "confianza": 0.9},
    ]))["no_shows"]
    assert vv.metodo == "medido"  # inferido de fuente="migracion_excel", no forzado


def test_hoja_estimada_no_contamina_otra_hoja_de_la_misma_migracion():
    df_estimada = pd.DataFrame({"automatizaciones_activas": [2]})
    df_medida = pd.DataFrame({"no_shows": [1, 0, 1]})
    variables = aplicar_mapeo(df_estimada, {
        "hoja": "Operativo", "fila_encabezado": 0, "hoja_estimada": True,
        "mapeo": [{"columna_index": 0, "variable": "automatizaciones_activas", "agregacion": "sum", "confianza": 0.8}],
    })
    variables = aplicar_mapeo(df_medida, _mapeo_hoja([
        {"columna_index": 0, "variable": "no_shows", "agregacion": "sum", "confianza": 0.9},
    ], hoja="Resumen"), variables)
    assert variables["automatizaciones_activas"].metodo == "estimado"
    assert variables["no_shows"].metodo == "medido"


# ---------------------------------------------------------------------------
# Fase H4b: bloque "ledger" en una hoja transaccional
# ---------------------------------------------------------------------------

def test_armar_registros_un_evento_simple():
    df = pd.DataFrame({
        "id_paciente": ["P1001", "P1001", "P1002"],
        "fecha": ["2026-01-05", "2026-03-10", "2026-02-01"],
        "monto": [50000, 80000, 30000],
        "concepto": ["Control", "Limpieza", "Urgencia"],
    })
    ledger_bloque = {
        "columna_paciente_index": 0, "id_estable": True, "columna_fecha_index": 1,
        "eventos": [{"tipo_evento": "pago", "columna_monto_index": 2, "columna_tratamiento_index": 3}],
    }
    registros = _armar_registros_ledger(df, ledger_bloque)
    assert len(registros) == 3
    assert registros[0] == {"paciente": "P1001", "fecha": "2026-01-05", "tipo_evento": "pago", "monto": 50000, "tratamiento": "Control"}


def test_armar_registros_condicion_genera_dos_eventos_por_fila_aceptada():
    df = pd.DataFrame({
        "id_paciente": ["P1001", "P1002"],
        "fecha": ["2026-01-05", "2026-01-06"],
        "monto": [100000, 50000],
        "estado": ["aceptado", "pendiente"],
    })
    ledger_bloque = {
        "columna_paciente_index": 0, "id_estable": True, "columna_fecha_index": 1,
        "eventos": [
            {"tipo_evento": "presupuesto_emitido", "columna_monto_index": 2},
            {"tipo_evento": "presupuesto_aceptado", "columna_monto_index": 2, "condicion": "estado == 'aceptado'"},
        ],
    }
    registros = _armar_registros_ledger(df, ledger_bloque)
    tipos_p1001 = sorted(r["tipo_evento"] for r in registros if r["paciente"] == "P1001")
    tipos_p1002 = sorted(r["tipo_evento"] for r in registros if r["paciente"] == "P1002")
    assert tipos_p1001 == ["presupuesto_aceptado", "presupuesto_emitido"]
    assert tipos_p1002 == ["presupuesto_emitido"]


def test_armar_registros_condicion_irresoluble_descarta_solo_ese_evento():
    df = pd.DataFrame({"id": ["P1"], "fecha": ["2026-01-01"], "monto": [100], "Estado turno": ["aceptado"]})
    ledger_bloque = {
        "columna_paciente_index": 0, "id_estable": True, "columna_fecha_index": 1,
        "eventos": [
            {"tipo_evento": "pago", "columna_monto_index": 2},
            {"tipo_evento": "presupuesto_aceptado", "columna_monto_index": 2, "condicion": "estado == 'aceptado'"},
        ],
    }
    registros = _armar_registros_ledger(df, ledger_bloque)
    assert [r["tipo_evento"] for r in registros] == ["pago"]  # nunca el "aceptado" sin filtrar


def test_armar_registros_sin_columnas_de_ledger_da_vacio():
    df = pd.DataFrame({"a": [1]})
    assert _armar_registros_ledger(df, {}) == []


def test_fusionar_ledger_junta_eventos_del_mismo_paciente_de_dos_hojas():
    existente = {"P1": [{"periodo": "2026-01", "tipo_evento": "turno_asistido"}]}
    nuevo = {"P1": [{"periodo": "2026-02", "tipo_evento": "pago"}], "P2": [{"periodo": "2026-01", "tipo_evento": "pago"}]}
    fusionado = _fusionar_ledger(existente, nuevo)
    assert [e["periodo"] for e in fusionado["P1"]] == ["2026-01", "2026-02"]
    assert len(fusionado["P2"]) == 1


def test_fusionar_ledger_sin_existente_devuelve_el_nuevo():
    nuevo = {"P1": [{"periodo": "2026-01", "tipo_evento": "pago"}]}
    assert _fusionar_ledger(None, nuevo) == nuevo


class _PuertoLLMFalso:
    """Fake de PuertoLLM: .preguntar(...) devuelve directamente el texto
    (JSON serializado) que excel_parser espera, sin pasar por
    anthropic.Anthropic ni por client.messages.create."""

    def __init__(self, payload: dict):
        self._texto = json.dumps(payload)

    def preguntar(self, **kwargs) -> str:
        return self._texto


def _csv_temporal(contenido: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", newline="")
    f.write(contenido)
    f.close()
    return f.name


def test_parsear_excel_end_to_end_arma_ledger_con_mapeo_vacio():
    """El caso real de cobros_historico.csv: ninguna columna es un total
    agregable (todo es historial por paciente), "mapeo" viene vacío y
    únicamente el bloque "ledger" trae la información — antes de H4b la
    guarda `not mapeo_hoja.get("mapeo")` salteaba la hoja entera."""
    path = _csv_temporal(
        "id_paciente,fecha_hora,monto_ars,concepto\n"
        "P1001,2026-01-05,50000,Control\n"
        "P1001,2026-03-10,80000,Limpieza\n"
        "P1002,2026-02-01,30000,Urgencia\n"
    )
    payload = {"hojas": [{
        "hoja": None, "fila_encabezado": 0, "orientacion": "transaccional",
        "mapeo": [],
        "ledger": {
            "columna_paciente_index": 0, "id_estable": True, "columna_fecha_index": 1,
            "eventos": [{"tipo_evento": "pago", "columna_monto_index": 2, "columna_tratamiento_index": 3, "confianza": 0.85}],
        },
    }]}
    variables, _ = parsear_excel(path, _PuertoLLMFalso(payload))
    ledger = variables["ledger_pacientes"].valor
    assert set(ledger.keys()) == {"P1001", "P1002"}
    assert len(ledger["P1001"]) == 2
    assert len(ledger["P1002"]) == 1
    assert variables["ledger_pacientes"].confianza == 0.85
    assert variables["ledger_pacientes"].fuente == "migracion_excel"
    Path(path).unlink()


def test_parsear_excel_ledger_y_mapeo_normal_conviven_en_la_misma_hoja():
    path = _csv_temporal(
        "id_paciente,fecha,monto\n"
        "P1001,2026-01-05,50000\n"
        "P1002,2026-01-06,30000\n"
    )
    payload = {"hojas": [{
        "hoja": None, "fila_encabezado": 0, "orientacion": "transaccional", "columna_periodo": 1,
        "mapeo": [{"columna_index": 2, "variable": "monto_cobrado", "agregacion": "sum", "confianza": 0.9}],
        "ledger": {
            "columna_paciente_index": 0, "id_estable": True, "columna_fecha_index": 1,
            "eventos": [{"tipo_evento": "pago", "columna_monto_index": 2}],
        },
    }]}
    variables, _ = parsear_excel(path, _PuertoLLMFalso(payload))
    assert variables["monto_cobrado"].valor == 80000.0
    assert set(variables["ledger_pacientes"].valor.keys()) == {"P1001", "P1002"}
    Path(path).unlink()


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
