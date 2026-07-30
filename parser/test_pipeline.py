"""
test_pipeline.py

Sin pytest: corre con `python3 test_pipeline.py`.
Cubre el enhebrado de RegistroClientes (Fase 2) a través de
pipeline.extraer_archivo/procesar_migracion: que solo se le pase a
extractores que lo declaran en su firma, que un mismo registro se
comparta entre archivos de una migración, y que los matches ambiguos
terminen en conflictos_pendientes — el mismo canal que ya usa conflictos.py.

Usa extractores falsos (no llama a la API real) para poder probar el
enhebrado de parámetros de forma determinista.
"""

import pipeline
from coverage import VariableValue
from matching import RegistroClientes


def _restaurar_extractores(original):
    pipeline.EXTRACTOR_POR_EXTENSION = original


def test_extraer_archivo_solo_pasa_registro_a_quien_lo_declara():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)
    llamadas = {}

    def extractor_con_soporte(path, client, registro_clientes=None):
        llamadas["con_soporte"] = registro_clientes
        return {}, {}

    def extractor_sin_soporte(path, client):
        llamadas["sin_soporte"] = "llamado"
        return {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": extractor_con_soporte, ".png": extractor_sin_soporte}
    try:
        registro = RegistroClientes()
        pipeline.extraer_archivo("clinica.xlsx", client=None, registro_clientes=registro)
        pipeline.extraer_archivo("foto.png", client=None, registro_clientes=registro)

        assert llamadas["con_soporte"] is registro
        assert llamadas["sin_soporte"] == "llamado"  # no explotó por recibir un kwarg que no acepta
    finally:
        _restaurar_extractores(original)


def test_mismo_registro_se_comparte_entre_archivos_de_una_migracion():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)
    registros_vistos = []

    def extractor_fake(path, client, registro_clientes=None):
        registros_vistos.append(registro_clientes)
        return {}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": extractor_fake}
    try:
        pipeline.procesar_migracion(["archivo1.xlsx", "archivo2.xlsx"], client=None)
        assert len(registros_vistos) == 2
        assert registros_vistos[0] is registros_vistos[1], "los dos archivos deben compartir el mismo RegistroClientes"
    finally:
        _restaurar_extractores(original)


def test_matches_ambiguos_llegan_a_conflictos_pendientes():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_que_deja_ambiguo(path, client, registro_clientes=None):
        # Simula lo que aplicar_mapeo haría al toparse con una zona gris real.
        registro_clientes.ambiguos.append({
            "nombre": "Juana Perez", "cliente_id_provisorio": "pac_xxx",
            "candidato_existente": "Juan Perez", "similitud": 0.952, "periodo": None,
        })
        variables = {"consultas_nuevas_mes": VariableValue(50, "migracion_excel", 0.9)}
        return variables, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": extractor_que_deja_ambiguo}
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], client=None)
        pendientes_paciente = [c for c in resultado["conflictos_pendientes"] if c["variable"] == "identidad_paciente"]
        assert len(pendientes_paciente) == 1
        assert "Juana Perez" in pendientes_paciente[0]["pregunta"]
        assert "Juan Perez" in pendientes_paciente[0]["pregunta"]
        assert pendientes_paciente[0]["similitud"] == 0.952
    finally:
        _restaurar_extractores(original)


def test_sin_ambiguos_no_agrega_nada_a_conflictos_pendientes():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_limpio(path, client, registro_clientes=None):
        return {"consultas_nuevas_mes": VariableValue(50, "migracion_excel", 0.9)}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": extractor_limpio}
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], client=None)
        assert resultado["conflictos_pendientes"] == []
    finally:
        _restaurar_extractores(original)


def test_sin_respuestas_diagnostico_diagnostico_queda_en_none():
    # Backward compat: nadie pasaba este argumento antes de la Fase 6 —
    # el default no debe ejecutar nada nuevo.
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_con_kpi4(path, client, registro_clientes=None):
        return {
            "no_shows": VariableValue(40, "migracion_excel", 0.9),
            "turnos_agendados": VariableValue(100, "migracion_excel", 0.9),
        }, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": extractor_con_kpi4}
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], client=None)
        assert resultado["diagnostico"] is None
        assert resultado["oportunidades_priorizadas"] is None
    finally:
        _restaurar_extractores(original)


def test_con_respuestas_diagnostico_cablea_diagnostico_y_oportunidades():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_con_kpi4(path, client, registro_clientes=None):
        return {
            "no_shows": VariableValue(40, "migracion_excel", 0.9),  # 40% de no-show: KPI4 bien fuera de rango (8-15)
            "turnos_agendados": VariableValue(100, "migracion_excel", 0.9),
        }, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": extractor_con_kpi4}
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], client=None, respuestas_diagnostico={})
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

    def extractor_con_cruce(path, client, registro_clientes=None):
        serie_monto = {"2026-01": 4000000.0, "2026-02": 5000000.0}
        serie_pacientes = {"2026-01": 50.0, "2026-02": 60.0}
        return {
            "monto_cobrado": VariableValue(5000000, "migracion_excel", 0.9, serie=serie_monto),
            "pacientes_atendidos_periodo": VariableValue(60, "migracion_excel", 0.9, serie=serie_pacientes),
        }, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": extractor_con_cruce}
    try:
        sin_respuestas = pipeline.procesar_migracion(["clinica.xlsx"], client=None)
        assert sin_respuestas["diagnostico"] is None  # esto sí depende de respuestas_diagnostico
        assert any(
            c.variable_a == "monto_cobrado" and c.variable_b == "pacientes_atendidos_periodo"
            for c in sin_respuestas["cruces"]
        ), "el cruce debe existir aunque no se hayan cargado respuestas de la Guía"

        con_respuestas = pipeline.procesar_migracion(["clinica.xlsx"], client=None, respuestas_diagnostico={})
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


def test_con_ledger_de_pagos_kpi14_se_calcula_y_es_trazable():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_con_ledger(path, client, registro_clientes=None):
        return {"ledger_pacientes": VariableValue(_ledger_con_pagos(), "migracion_excel", 0.9)}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".csv": extractor_con_ledger}
    try:
        resultado = pipeline.procesar_migracion(["cobros.csv"], client=None)
        assert 14 in resultado["kpis_calculados"]
        ingreso = resultado["variables"]["ingreso_por_paciente"]
        assert ingreso.valor == {"P1": 130000.0, "P2": 30000.0}
        assert ingreso.fuente == "ledger_pacientes"
        assert resultado["metricas_paciente"] is not None
        assert resultado["metricas_paciente"]["ltv_real"] == {"P1": 130000.0, "P2": 30000.0}
    finally:
        _restaurar_extractores(original)


def test_ledger_sin_pagos_kpi14_sigue_bloqueado_pero_metricas_no_es_none():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)
    ledger_sin_pagos = {"P1": [{"periodo": "2026-01", "tipo_evento": "turno_asistido", "monto": None, "tratamiento": None}]}

    def extractor_sin_pagos(path, client, registro_clientes=None):
        return {"ledger_pacientes": VariableValue(ledger_sin_pagos, "migracion_excel", 0.9)}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".csv": extractor_sin_pagos}
    try:
        resultado = pipeline.procesar_migracion(["turnos.csv"], client=None)
        assert 14 not in resultado["kpis_calculados"]
        assert "ingreso_por_paciente" not in resultado["variables"]
        assert resultado["metricas_paciente"] is not None  # el ledger existe, aunque ltv_real de vacío
        assert resultado["metricas_paciente"]["ltv_real"] == {}
    finally:
        _restaurar_extractores(original)


def test_sin_ledger_metricas_paciente_es_none_y_nada_mas_cambia():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_limpio(path, client, registro_clientes=None):
        return {"consultas_nuevas_mes": VariableValue(50, "migracion_excel", 0.9)}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": extractor_limpio}
    try:
        resultado = pipeline.procesar_migracion(["clinica.xlsx"], client=None)
        assert resultado["metricas_paciente"] is None
        assert "ingreso_por_paciente" not in resultado["variables"]
    finally:
        _restaurar_extractores(original)


def test_ledger_no_pisa_ingreso_por_paciente_ya_extraido():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_con_ledger(path, client, registro_clientes=None):
        return {
            "ledger_pacientes": VariableValue(_ledger_con_pagos(), "migracion_excel", 0.9),
            "ingreso_por_paciente": VariableValue({"P9": 999.0}, "migracion_excel", 0.9),
        }, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".csv": extractor_con_ledger}
    try:
        resultado = pipeline.procesar_migracion(["cobros.csv"], client=None)
        assert resultado["variables"]["ingreso_por_paciente"].valor == {"P9": 999.0}
    finally:
        _restaurar_extractores(original)


def test_dos_archivos_con_ledger_se_fusionan_en_vez_de_generar_conflicto():
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_cobros(path, client, registro_clientes=None):
        return {"ledger_pacientes": VariableValue(
            {"P1": [{"periodo": "2026-01", "tipo_evento": "pago", "monto": 50000, "tratamiento": None}]},
            "migracion_excel", 0.9,
        )}, {}

    def extractor_turnos(path, client, registro_clientes=None):
        return {"ledger_pacientes": VariableValue(
            {"P1": [{"periodo": "2026-01", "tipo_evento": "turno_asistido", "monto": None, "tratamiento": None}],
             "P2": [{"periodo": "2026-02", "tipo_evento": "turno_no_show", "monto": None, "tratamiento": None}]},
            "migracion_excel", 0.85,
        )}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".csv": extractor_cobros, ".xlsx": extractor_turnos}
    try:
        resultado = pipeline.procesar_migracion(["cobros.csv", "turnos.xlsx"], client=None)
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
    from conflictos import resolver_conflictos
    fuentes = [
        {"no_shows": VariableValue(56, "migracion_excel", 0.8, archivo_origen="a.xlsx")},
        {"no_shows": VariableValue(60, "migracion_excel", 0.75, archivo_origen="b.xlsx")},
    ]
    original = dict(pipeline.EXTRACTOR_POR_EXTENSION)

    def extractor_a(path, client, registro_clientes=None):
        return {"no_shows": VariableValue(56, "migracion_excel", 0.8, archivo_origen="a.xlsx")}, {}

    def extractor_b(path, client, registro_clientes=None):
        return {"no_shows": VariableValue(60, "migracion_excel", 0.75, archivo_origen="b.xlsx")}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": extractor_a, ".csv": extractor_b}
    try:
        resultado = pipeline.procesar_migracion(["a.xlsx", "b.csv"], client=None)
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

    def extractor_discrepante(path, client, registro_clientes=None):
        return {"no_shows": VariableValue(99, "migracion_excel", 0.9, archivo_origen="nuevo.xlsx")}, {}

    pipeline.EXTRACTOR_POR_EXTENSION = {".xlsx": extractor_discrepante}
    try:
        resultado2 = pipeline.procesar_migracion(
            ["nuevo.xlsx"], variables_previas=resultado["variables"], client=None,
        )
        pendiente = next(c for c in resultado2["conflictos_pendientes"] if c["variable"] == "no_shows")
        assert "56" in pendiente["pregunta"]
        assert "99" in pendiente["pregunta"]
        assert "nuevo.xlsx" in pendiente["pregunta"]
    finally:
        _restaurar_extractores(original)


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
