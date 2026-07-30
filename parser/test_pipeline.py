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


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
