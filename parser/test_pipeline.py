"""
test_pipeline.py

Sin pytest: corre con `python -m parser.test_pipeline`.
Cubre el enhebrado de RegistroClientes (Fase 2) a través de
pipeline.extraer_archivo/procesar_migracion — que un mismo registro se
comparta entre archivos de una migración, y que los matches ambiguos
terminen en conflictos_pendientes (el mismo canal que ya usa
conflictos.py) — y, desde la Fase Strategy+Adapter, que
`EXTRACTOR_POR_EXTENSION` funcione con objetos `EstrategiaExtraccion`
(`.extraer(path, puerto_llm, *, registro_clientes=None) ->
ResultadoExtraccion`) en vez de funciones sueltas: `registro_clientes` ya
no se detecta por introspección (`inspect.signature`), se pasa siempre —
las estrategias que no lo usan simplemente lo ignoran.

Usa estrategias falsas (no llama a la API real, `puerto_llm=None` alcanza
porque nunca se dispara una llamada real) para poder probar el enhebrado
de parámetros de forma determinista.
"""

from types import SimpleNamespace

from parser import pipeline
from parser.cobertura_calidad.coverage import VariableValue
from parser.extraccion.estrategias import ResultadoExtraccion
from parser.pacientes.matching import RegistroClientes
from parser.vocabulario.puerto_geometria import FilaGeometrica


def _restaurar_extractores(original):
    pipeline.EXTRACTOR_POR_EXTENSION = original


def _estrategia(fn):
    """Envuelve una función de test `(path, puerto_llm, *, registro_clientes=None)
    -> (variables, tasas_declaradas)` en un objeto con `.extraer` que ya
    devuelve `ResultadoExtraccion` — la misma forma que produce una
    `EstrategiaExtraccion` real, sin tener que declarar una clase nueva
    por cada test."""

    def extraer(path, puerto_llm, *, registro_clientes=None):
        variables, tasas_declaradas = fn(path, puerto_llm, registro_clientes=registro_clientes)
        return ResultadoExtraccion(variables=variables, tasas_declaradas=tasas_declaradas)

    return SimpleNamespace(extraer=extraer)


def test_extraer_archivo_pasa_registro_clientes_uniformemente_a_toda_estrategia():
    # Fase Strategy+Adapter: `registro_clientes` ya no se detecta por
    # firma (inspect.signature) — el contrato EstrategiaExtraccion lo
    # declara siempre, así que toda estrategia lo recibe, la use o no
    # (antes sólo lo recibía quien lo declaraba explícito en su función).
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)
    llamadas = {}

    def extractor_que_usa_registro(path, puerto_llm, registro_clientes=None):
        llamadas["usa_registro"] = registro_clientes
        return {}, {}

    def extractor_que_lo_ignora(path, puerto_llm, registro_clientes=None):
        llamadas["lo_ignora"] = registro_clientes
        return {}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {
        ".xlsx": _estrategia(extractor_que_usa_registro),
        ".png": _estrategia(extractor_que_lo_ignora),
    }
    try:
        registro = RegistroClientes()
        pipeline.extraer_archivo("clinica.xlsx", puerto_llm=None, registro_clientes=registro)
        pipeline.extraer_archivo("foto.png", puerto_llm=None, registro_clientes=registro)

        assert llamadas["usa_registro"] is registro
        assert llamadas["lo_ignora"] is registro, (
            "una estrategia que no usa registro_clientes igual debe recibirlo, "
            "sin romper — ya no es opcional por firma"
        )
    finally:
        _restaurar_extractores(original)


def test_mismo_registro_se_comparte_entre_archivos_de_una_migracion():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)
    registros_vistos = []

    def extractor_fake(path, puerto_llm, registro_clientes=None):
        registros_vistos.append(registro_clientes)
        return {}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_fake)}
    try:
        pipeline.procesar_migracion(["archivo1.xlsx", "archivo2.xlsx"], puerto_llm=None)
        assert len(registros_vistos) == 2
        assert registros_vistos[0] is registros_vistos[1], "los dos archivos deben compartir el mismo RegistroClientes"
    finally:
        _restaurar_extractores(original)


def test_matches_ambiguos_llegan_a_conflictos_pendientes():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_que_deja_ambiguo(path, puerto_llm, registro_clientes=None):
        # Simula lo que aplicar_mapeo haría al toparse con una zona gris real.
        registro_clientes.ambiguos.append({
            "nombre": "Juana Perez", "cliente_id_provisorio": "pac_xxx",
            "candidato_existente": "Juan Perez", "similitud": 0.952, "periodo": None,
        })
        variables = {"consultas_nuevas_mes": VariableValue(50, "migracion_excel", 0.9)}
        return variables, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_que_deja_ambiguo)}
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], puerto_llm=None)
        pendientes_paciente = [c for c in resultado["conflictos_pendientes"] if c["variable"] == "identidad_paciente"]
        assert len(pendientes_paciente) == 1
        assert "Juana Perez" in pendientes_paciente[0]["pregunta"]
        assert "Juan Perez" in pendientes_paciente[0]["pregunta"]
        assert pendientes_paciente[0]["similitud"] == 0.952
    finally:
        _restaurar_extractores(original)


def test_sin_ambiguos_no_agrega_nada_a_conflictos_pendientes():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_limpio(path, puerto_llm, registro_clientes=None):
        return {"consultas_nuevas_mes": VariableValue(50, "migracion_excel", 0.9)}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_limpio)}
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], puerto_llm=None)
        assert resultado["conflictos_pendientes"] == []
    finally:
        _restaurar_extractores(original)


def test_sin_respuestas_diagnostico_diagnostico_queda_en_none():
    # Backward compat: nadie pasaba este argumento antes de la Fase 6 —
    # el default no debe ejecutar nada nuevo.
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_con_kpi4(path, puerto_llm, registro_clientes=None):
        return {
            "no_shows": VariableValue(40, "migracion_excel", 0.9),
            "turnos_agendados": VariableValue(100, "migracion_excel", 0.9),
        }, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_con_kpi4)}
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], puerto_llm=None)
        assert resultado["diagnostico"] is None
        assert resultado["oportunidades_priorizadas"] is None
    finally:
        _restaurar_extractores(original)


def test_con_respuestas_diagnostico_cablea_diagnostico_y_oportunidades():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_con_kpi4(path, puerto_llm, registro_clientes=None):
        return {
            "no_shows": VariableValue(40, "migracion_excel", 0.9),  # 40% de no-show: KPI4 bien fuera de rango (8-15)
            "turnos_agendados": VariableValue(100, "migracion_excel", 0.9),
        }, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_con_kpi4)}
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], puerto_llm=None, respuestas_diagnostico={})
        assert resultado["diagnostico"] is not None
        assert any(d.kpi_id == 4 for d in resultado["diagnostico"])
        assert resultado["oportunidades_priorizadas"] is not None
        assert any(o.kpi_id == 4 for o in resultado["oportunidades_priorizadas"])
    finally:
        _restaurar_extractores(original)


def test_cruces_se_calculan_independientemente_de_respuestas_diagnostico():
    """Fase B: a diferencia de diagnóstico/oportunidades (Fases 4-6),
    resultado["cruces"] no depende de respuestas_diagnostico — corre
    siempre, porque es puramente determinista sobre las variables."""
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_con_cruce(path, puerto_llm, registro_clientes=None):
        serie_monto = {"2026-01": 4000000.0, "2026-02": 5000000.0}
        serie_pacientes = {"2026-01": 50.0, "2026-02": 60.0}
        return {
            "monto_cobrado": VariableValue(5000000, "migracion_excel", 0.9, serie=serie_monto),
            "pacientes_atendidos_periodo": VariableValue(60, "migracion_excel", 0.9, serie=serie_pacientes),
        }, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_con_cruce)}
    try:
        sin_respuestas = pipeline.procesar_migracion(["clinica.xlsx"], puerto_llm=None)
        assert sin_respuestas["diagnostico"] is None  # esto sí depende de respuestas_diagnostico
        assert any(
            c.variable_a == "monto_cobrado" and c.variable_b == "pacientes_atendidos_periodo"
            for c in sin_respuestas["cruces"]
        ), "el cruce debe existir aunque no se hayan cargado respuestas de la Guía"

        con_respuestas = pipeline.procesar_migracion(["clinica.xlsx"], puerto_llm=None, respuestas_diagnostico={})
        assert len(con_respuestas["cruces"]) == len(sin_respuestas["cruces"])
    finally:
        _restaurar_extractores(original)


# ---------------------------------------------------------------------------
# Fase G5a: resolver_conflicto no reenviaba respuestas_diagnostico — el
# dueño resolvía un conflicto para ganar un KPI y en el mismo movimiento
# perdía el diagnóstico y las oportunidades que ya tenía calculados.
# ---------------------------------------------------------------------------

def test_resolver_conflicto_sin_respuestas_diagnostico_no_lo_ejecuta():
    """Mismo comportamiento de siempre (backward compat): sin pasar el
    parámetro nuevo, sigue devolviendo diagnostico=None."""
    variables_previas = {
        "turnos_agendados": VariableValue(100, "migracion_excel", 0.9),
    }
    resultado = pipeline.resolver_conflicto("no_shows", variables_previas, valor=40)
    assert resultado["variables"]["no_shows"].fuente == "confirmado_por_dueno"
    assert resultado["diagnostico"] is None
    assert resultado["oportunidades_priorizadas"] is None


def test_resolver_conflicto_con_respuestas_diagnostico_las_cablea():
    """La prueba directa del bug: resolver un conflicto pasando las
    respuestas ya cargadas debe devolver diagnostico y oportunidades
    poblados, no perderlos."""
    variables_previas = {
        "turnos_agendados": VariableValue(100, "migracion_excel", 0.9),
    }
    resultado = pipeline.resolver_conflicto(
        "no_shows", variables_previas, valor=40,  # 40% de no-show: KPI 4 bien fuera de rango
        respuestas_diagnostico={},
    )
    assert resultado["variables"]["no_shows"].fuente == "confirmado_por_dueno"
    assert resultado["diagnostico"] is not None
    assert any(d.kpi_id == 4 for d in resultado["diagnostico"])
    assert resultado["oportunidades_priorizadas"] is not None


# ---------------------------------------------------------------------------
# Fase H4c: derivar ingreso_por_paciente + exponer metricas_paciente
# ---------------------------------------------------------------------------

def _ledger_con_pagos():
    return {
        "P1": [
            {"periodo": "2026-01", "tipo_evento": "pago", "monto": 50000, "tratamiento": "Control"},
            {"periodo": "2026-03", "tipo_evento": "pago", "monto": 80000, "tratamiento": "Limpieza"},
        ],
        "P2": [{"periodo": "2026-02", "tipo_evento": "pago", "monto": 30000, "tratamiento": "Urgencia"}],
    }


def test_con_ledger_de_pagos_ingreso_por_paciente_se_deriva_y_es_trazable():
    # El KPI 14 (Valor del paciente/LTV) que antes leía esta variable se
    # podó en Slice 2 — ingreso_por_paciente ya no cae en kpis_calculados
    # de ningún KPIFormula, pero sigue derivándose de ltv_real() para
    # alimentar resultado["metricas_paciente"] y quedar trazable.
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_con_ledger(path, puerto_llm, registro_clientes=None):
        return {"ledger_pacientes": VariableValue(_ledger_con_pagos(), "migracion_excel", 0.9)}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".csv": _estrategia(extractor_con_ledger)}
    try:
        resultado = pipeline.procesar_migracion(["cobros.csv"], puerto_llm=None)
        assert 14 not in resultado["kpis_calculados"], "KPI 14 se podó en Slice 2, nunca debería aparecer"
        ingreso = resultado["variables"]["ingreso_por_paciente"]
        assert ingreso.valor == {"P1": 130000.0, "P2": 30000.0}
        assert ingreso.fuente == "ledger_pacientes"
        assert resultado["metricas_paciente"] is not None
        assert resultado["metricas_paciente"]["ltv_real"] == {"P1": 130000.0, "P2": 30000.0}
    finally:
        _restaurar_extractores(original)


def test_ledger_sin_pagos_no_deriva_ingreso_pero_metricas_no_es_none():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)
    ledger_sin_pagos = {"P1": [{"periodo": "2026-01", "tipo_evento": "turno_asistido", "monto": None, "tratamiento": None}]}

    def extractor_sin_pagos(path, puerto_llm, registro_clientes=None):
        return {"ledger_pacientes": VariableValue(ledger_sin_pagos, "migracion_excel", 0.9)}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".csv": _estrategia(extractor_sin_pagos)}
    try:
        resultado = pipeline.procesar_migracion(["turnos.csv"], puerto_llm=None)
        assert 14 not in resultado["kpis_calculados"]
        assert "ingreso_por_paciente" not in resultado["variables"]
        assert resultado["metricas_paciente"] is not None  # el ledger existe, aunque ltv_real de vacío
        assert resultado["metricas_paciente"]["ltv_real"] == {}
    finally:
        _restaurar_extractores(original)


def test_sin_ledger_metricas_paciente_es_none_y_nada_mas_cambia():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_limpio(path, puerto_llm, registro_clientes=None):
        return {"consultas_nuevas_mes": VariableValue(50, "migracion_excel", 0.9)}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_limpio)}
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], puerto_llm=None)
        assert resultado["metricas_paciente"] is None
        assert "ingreso_por_paciente" not in resultado["variables"]
    finally:
        _restaurar_extractores(original)


def test_ledger_no_pisa_ingreso_por_paciente_ya_extraido():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_con_ledger(path, puerto_llm, registro_clientes=None):
        return {
            "ledger_pacientes": VariableValue(_ledger_con_pagos(), "migracion_excel", 0.9),
            "ingreso_por_paciente": VariableValue({"P9": 999.0}, "migracion_excel", 0.9),
        }, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".csv": _estrategia(extractor_con_ledger)}
    try:
        resultado = pipeline.procesar_migracion(["cobros.csv"], puerto_llm=None)
        assert resultado["variables"]["ingreso_por_paciente"].valor == {"P9": 999.0}
    finally:
        _restaurar_extractores(original)


def test_dos_archivos_con_ledger_se_fusionan_en_vez_de_generar_conflicto():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_cobros(path, puerto_llm, registro_clientes=None):
        return {"ledger_pacientes": VariableValue(
            {"P1": [{"periodo": "2026-01", "tipo_evento": "pago", "monto": 50000, "tratamiento": None}]},
            "migracion_excel", 0.9,
        )}, {}

    def extractor_turnos(path, puerto_llm, registro_clientes=None):
        return {"ledger_pacientes": VariableValue(
            {"P1": [{"periodo": "2026-01", "tipo_evento": "turno_asistido", "monto": None, "tratamiento": None}],
             "P2": [{"periodo": "2026-02", "tipo_evento": "turno_no_show", "monto": None, "tratamiento": None}]},
            "migracion_excel", 0.85,
        )}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {
        ".csv": _estrategia(extractor_cobros), ".xlsx": _estrategia(extractor_turnos),
    }
    try:
        resultado = pipeline.procesar_migracion(["cobros.csv", "turnos.xlsx"], puerto_llm=None)
        assert resultado["conflictos_pendientes"] == []  # nunca un "conflicto" entre dos ledgers
        ledger = resultado["variables"]["ledger_pacientes"].valor
        assert len(ledger["P1"]) == 2  # el pago Y el turno_asistido, no uno pisando al otro
        assert "P2" in ledger
    finally:
        _restaurar_extractores(original)


# ---------------------------------------------------------------------------
# Fase I7: la pregunta de un conflicto nombra archivos/valores/períodos
# reales — antes eran 3 f-strings genéricas sin un solo dato concreto.
# ---------------------------------------------------------------------------

def test_pregunta_valores_distintos_nombra_los_valores_y_archivos():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_a(path, puerto_llm, registro_clientes=None):
        return {"no_shows": VariableValue(56, "migracion_excel", 0.8, archivo_origen="a.xlsx")}, {}

    def extractor_b(path, puerto_llm, registro_clientes=None):
        return {"no_shows": VariableValue(60, "migracion_excel", 0.75, archivo_origen="b.xlsx")}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_a), ".csv": _estrategia(extractor_b)}
    try:
        resultado = pipeline.procesar_migracion(["a.xlsx", "b.csv"], puerto_llm=None)
        pendiente = next(c for c in resultado["conflictos_pendientes"] if c["variable"] == "no_shows")
        assert "56" in pendiente["pregunta"]
        assert "60" in pendiente["pregunta"]
        # extraer_archivo pisa archivo_origen con el nombre real del path de
        # entrada (Path(path).name) — eso es lo que termina en la pregunta,
        # no lo que el extractor haya seteado internamente.
        assert "a.xlsx" in pendiente["pregunta"]
        assert "b.csv" in pendiente["pregunta"]
    finally:
        _restaurar_extractores(original)


def test_pregunta_contradice_confirmado_nombra_el_valor_confirmado():
    resultado = pipeline.resolver_conflicto(
        "no_shows", {}, valor=56,
    )
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_discrepante(path, puerto_llm, registro_clientes=None):
        return {"no_shows": VariableValue(99, "migracion_excel", 0.9, archivo_origen="nuevo.xlsx")}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_discrepante)}
    try:
        resultado2 = pipeline.procesar_migracion(
            ["nuevo.xlsx"], variables_previas=resultado["variables"], puerto_llm=None,
        )
        pendiente = next(c for c in resultado2["conflictos_pendientes"] if c["variable"] == "no_shows")
        assert "56" in pendiente["pregunta"]
        assert "99" in pendiente["pregunta"]
        assert "nuevo.xlsx" in pendiente["pregunta"]
    finally:
        _restaurar_extractores(original)


def test_un_archivo_que_explota_no_tira_abajo_la_migracion_de_los_demas():
    # Bug real: control_recall_junio2026.png hacía explotar vision_parser
    # con un JSONDecodeError sin capturar, y eso tiraba abajo TODA la
    # migración aunque otros archivos (xlsx, csv) fueran perfectamente
    # procesables. extraer_archivo ahora se llama dentro de un try/except
    # por archivo — este test fija ese comportamiento con una estrategia
    # que explota de verdad, sin mockear json.loads.
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_ok(path, puerto_llm, registro_clientes=None):
        return {
            "no_shows": VariableValue(40, "migracion_excel", 0.9),
            "turnos_agendados": VariableValue(100, "migracion_excel", 0.9),
        }, {}

    def extractor_que_explota(path, puerto_llm, registro_clientes=None):
        raise ValueError("JSON inválido, no se pudo parsear la respuesta de Claude")

    pipeline.EXTRACTOR_POR_EXTENSION = {
        ".xlsx": _estrategia(extractor_ok), ".png": _estrategia(extractor_que_explota),
    }
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx", "control_recall.png"], puerto_llm=None)

        assert len(resultado["archivos_fallidos"]) == 1
        assert resultado["archivos_fallidos"][0]["archivo"] == "control_recall.png"
        assert "JSON inválido" in resultado["archivos_fallidos"][0]["error"]

        # El archivo que sí funcionó no se pierde: sus variables llegan
        # igual a KPIs calculados.
        assert 4 in resultado["kpis_calculados"]
    finally:
        _restaurar_extractores(original)


def test_todos_los_archivos_fallan_no_rompe_devuelve_migracion_vacia():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_que_explota(path, puerto_llm, registro_clientes=None):
        raise RuntimeError("timeout de red")

    pipeline.EXTRACTOR_POR_EXTENSION = {".png": _estrategia(extractor_que_explota)}
    try:
        resultado = pipeline.procesar_migracion(["a.png", "b.png"], puerto_llm=None)
        assert len(resultado["archivos_fallidos"]) == 2
        assert resultado["kpis_calculados"] == {}
    finally:
        _restaurar_extractores(original)


# ---------------------------------------------------------------------------
# Bug #2 (E2E): _segunda_lectura_para_variables_dudosas siempre llamaba
# excel_parser.leer_hojas_crudas(path), que para una foto/PDF explota (no es
# un archivo de Excel) -> se capturaba en silencio -> la variable de foto
# quedaba sin segunda lectura para siempre. Ahora se branchea por
# `fuente == "migracion_foto"` hacia segunda_lectura.pedir_segunda_lectura_imagen.
# ---------------------------------------------------------------------------

def test_segunda_lectura_de_variable_de_foto_usa_relectura_de_imagen_no_grid_de_excel():
    original_extractores = dict(pipeline.EXTRACTOR_POR_EXTENSION)
    llamadas_grid = []
    llamadas_imagen = []

    def extractor_foto(path, puerto_llm, registro_clientes=None):
        return {"no_shows": VariableValue(16, "migracion_foto", 0.5)}, {}

    def leer_hojas_crudas_espia(path):
        llamadas_grid.append(path)
        return []

    def pedir_segunda_lectura_imagen_espia(path, variables, puerto_llm):
        llamadas_imagen.append((path, variables))
        return {"no_shows": {"variable": "no_shows", "valor": 16, "confianza": 0.8}}

    pipeline.EXTRACTOR_POR_EXTENSION = {".png": _estrategia(extractor_foto)}
    original_leer_hojas = pipeline.excel_parser.leer_hojas_crudas
    original_pedir_imagen = pipeline.segunda_lectura.pedir_segunda_lectura_imagen
    pipeline.excel_parser.leer_hojas_crudas = leer_hojas_crudas_espia
    pipeline.segunda_lectura.pedir_segunda_lectura_imagen = pedir_segunda_lectura_imagen_espia
    try:
        resultado = pipeline.procesar_migracion(["foto.png"], puerto_llm=object())
        assert llamadas_imagen == [("foto.png", ["no_shows"])]
        assert llamadas_grid == [], "una variable migracion_foto no debe pasar por leer_hojas_crudas"
        assert resultado["variables"]["no_shows"].confianza == 0.7  # 0.5 + 0.2 (coincide)
    finally:
        pipeline.EXTRACTOR_POR_EXTENSION = original_extractores
        pipeline.excel_parser.leer_hojas_crudas = original_leer_hojas
        pipeline.segunda_lectura.pedir_segunda_lectura_imagen = original_pedir_imagen


def test_segunda_lectura_de_foto_que_no_coincide_no_sube_confianza():
    original_extractores = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_foto(path, puerto_llm, registro_clientes=None):
        return {"no_shows": VariableValue(57, "migracion_foto", 0.5)}, {}

    def pedir_segunda_lectura_imagen_espia(path, variables, puerto_llm):
        # La relectura ciega dice otra cosa — no coincide dentro del 5%.
        return {"no_shows": {"variable": "no_shows", "valor": 16, "confianza": 0.8}}

    pipeline.EXTRACTOR_POR_EXTENSION = {".png": _estrategia(extractor_foto)}
    original_pedir_imagen = pipeline.segunda_lectura.pedir_segunda_lectura_imagen
    pipeline.segunda_lectura.pedir_segunda_lectura_imagen = pedir_segunda_lectura_imagen_espia
    try:
        resultado = pipeline.procesar_migracion(["foto.png"], puerto_llm=object())
        assert resultado["variables"]["no_shows"].confianza == 0.5, "sin coincidencia, la confianza no sube"
    finally:
        pipeline.EXTRACTOR_POR_EXTENSION = original_extractores
        pipeline.segunda_lectura.pedir_segunda_lectura_imagen = original_pedir_imagen


def test_segunda_lectura_de_variable_de_planilla_sigue_usando_el_grid_de_excel():
    # Regresión: separar por fuente no debe hacer que una variable de Excel
    # empiece a pasar por la relectura de imagen.
    original_extractores = dict(pipeline.EXTRACTOR_POR_EXTENSION)
    llamadas_grid = []
    llamadas_imagen = []

    def extractor_planilla(path, puerto_llm, registro_clientes=None):
        return {"no_shows": VariableValue(16, "migracion_excel", 0.5)}, {}

    def leer_hojas_crudas_espia(path):
        llamadas_grid.append(path)
        return []  # no hace falta simular un grid real para esta regresión

    def pedir_segunda_lectura_imagen_espia(path, variables, puerto_llm):
        llamadas_imagen.append((path, variables))
        return {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_planilla)}
    original_leer_hojas = pipeline.excel_parser.leer_hojas_crudas
    original_pedir_imagen = pipeline.segunda_lectura.pedir_segunda_lectura_imagen
    pipeline.excel_parser.leer_hojas_crudas = leer_hojas_crudas_espia
    pipeline.segunda_lectura.pedir_segunda_lectura_imagen = pedir_segunda_lectura_imagen_espia
    try:
        pipeline.procesar_migracion(["clinica.xlsx"], puerto_llm=object())
        assert llamadas_grid == ["clinica.xlsx"], "el camino de Excel debe seguir llamando a leer_hojas_crudas"
        assert llamadas_imagen == [], "una variable migracion_excel no debe pasar por la relectura de imagen"
    finally:
        pipeline.EXTRACTOR_POR_EXTENSION = original_extractores
        pipeline.excel_parser.leer_hojas_crudas = original_leer_hojas
        pipeline.segunda_lectura.pedir_segunda_lectura_imagen = original_pedir_imagen


# ---------------------------------------------------------------------------
# Fase 3 (Bug #1a, PR 3): _verificacion_geometria_fotos — con
# puerto_geometria=None (default) el paso es un no-op completo; con un
# _PuertoGeometriaFalso, un acuerdo sube confianza y un desacuerdo la deja
# igual y surge por el mismo canal que un mismatch de segunda_lectura
# (variables_a_confirmar); nunca corre para Excel/PDF.
# ---------------------------------------------------------------------------

class _PuertoGeometriaFalso:
    """Fake de PuertoGeometria: mismo espíritu que _PuertoGeometriaFalso en
    parser/extraccion/test_geometria.py, replicado acá (sin import cruzado
    entre módulos de test, misma convención que el resto del archivo) —
    .ordenar_filas(path) devuelve la lista de FilaGeometrica preseteada,
    sin llamar a ningún vendor real."""

    def __init__(self, filas: list[FilaGeometrica]):
        self._filas = filas
        self.ultimo_path = None

    def ordenar_filas(self, path: str) -> list[FilaGeometrica]:
        self.ultimo_path = path
        return self._filas


def test_geometria_off_deja_variables_byte_identicas_a_antes_del_cambio():
    # Regresión (Req 3 del spec): puerto_geometria=None es el default y el
    # único valor que procesar_migracion recibe hoy en producción — el
    # paso nuevo no debe tocar nada.
    original_extractores = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_foto(path, puerto_llm, registro_clientes=None):
        vv = VariableValue(16, "migracion_foto", 0.9)
        vv.etiqueta_fila = "No-shows"
        return {"no_shows": vv}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".png": _estrategia(extractor_foto)}
    try:
        resultado = pipeline.procesar_migracion(["foto.png"], puerto_llm=None)
        assert resultado["variables"]["no_shows"].confianza == 0.9, "sin puerto_geometria, la confianza no cambia"
        assert resultado["variables"]["no_shows"].valor == 16
    finally:
        pipeline.EXTRACTOR_POR_EXTENSION = original_extractores


def test_geometria_con_orden_coincidente_sube_confianza():
    original_extractores = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_foto(path, puerto_llm, registro_clientes=None):
        vv = VariableValue(16, "migracion_foto", 0.5)
        vv.etiqueta_fila = "No-shows"
        return {"no_shows": vv}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".png": _estrategia(extractor_foto)}
    puerto_geometria = _PuertoGeometriaFalso([FilaGeometrica(etiqueta="No-shows", y_top=0.1, orden=0)])
    try:
        resultado = pipeline.procesar_migracion(["foto.png"], puerto_llm=None, puerto_geometria=puerto_geometria)
        assert resultado["variables"]["no_shows"].confianza == 0.7  # 0.5 + 0.2 (coincide)
        assert puerto_geometria.ultimo_path == "foto.png"
    finally:
        pipeline.EXTRACTOR_POR_EXTENSION = original_extractores


def test_geometria_con_orden_desacoplado_baja_confianza_alta_y_surge_como_discrepancia():
    original_extractores = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_foto(path, puerto_llm, registro_clientes=None):
        # no_shows arranca con confianza ALTA (0.9) a propósito: es
        # exactamente el escenario que motivó el Bug #1a — Claude
        # confiado, pero leyendo el valor de la fila equivocada. Si el
        # chequeo de geometría no bajara la confianza explícitamente acá
        # (a diferencia de segunda_lectura, que solo corre sobre
        # variables YA dudosas), este caso pasaría desapercibido: 0.9
        # nunca cruza el umbral de variables_baja_confianza por sí solo.
        # turnos_agendados completa el KPI4 (no_shows/turnos_agendados)
        # con confianza alta también, para que confianza_min del KPI
        # quede determinada por no_shows.
        vv_no_shows = VariableValue(16, "migracion_foto", 0.9)
        vv_no_shows.etiqueta_fila = "No-shows"
        return {
            "no_shows": vv_no_shows,
            "turnos_agendados": VariableValue(100, "migracion_foto", 0.95),
        }, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".png": _estrategia(extractor_foto)}
    # "no_shows" es la única (y por lo tanto primera, orden original 0)
    # variable con etiqueta_fila, pero la geometría la ubica en la fila 2
    # — un corrimiento de 2, mayor que la tolerancia default (1).
    puerto_geometria = _PuertoGeometriaFalso([
        FilaGeometrica(etiqueta="Turnos agendados", y_top=0.05, orden=0),
        FilaGeometrica(etiqueta="Cancelaciones", y_top=0.15, orden=1),
        FilaGeometrica(etiqueta="No-shows", y_top=0.25, orden=2),
    ])
    try:
        resultado = pipeline.procesar_migracion(["foto.png"], puerto_llm=None, puerto_geometria=puerto_geometria)
        assert resultado["variables"]["no_shows"].confianza < 0.7, (
            "un desacuerdo geométrico tiene que bajar la confianza explícitamente, "
            "aunque haya arrancado alta — si no, un misread confiado en la fila "
            "equivocada (el escenario real del Bug #1a) queda invisible"
        )
        # Mismo canal que un mismatch de segunda_lectura: confianza < 0.7
        # -> variables_baja_confianza -> variables_a_confirmar del payload.
        sugerencia = next(v for v in resultado["variables_a_confirmar"] if v["variable"] == "no_shows")
        assert sugerencia["valor_sugerido"] == 16
    finally:
        pipeline.EXTRACTOR_POR_EXTENSION = original_extractores


def test_geometria_no_corre_para_variables_de_excel_ni_pdf():
    original_extractores = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_excel(path, puerto_llm, registro_clientes=None):
        return {"consultas_nuevas_mes": VariableValue(50, "migracion_excel", 0.5)}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": _estrategia(extractor_excel)}
    puerto_geometria = _PuertoGeometriaFalso([FilaGeometrica(etiqueta="Consultas nuevas", y_top=0.1, orden=0)])
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], puerto_llm=None, puerto_geometria=puerto_geometria)
        assert resultado["variables"]["consultas_nuevas_mes"].confianza == 0.5, "Excel no pasa por geometría"
        assert puerto_geometria.ultimo_path is None, "ordenar_filas nunca debe llamarse para un archivo que no es foto"
    finally:
        pipeline.EXTRACTOR_POR_EXTENSION = original_extractores


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
