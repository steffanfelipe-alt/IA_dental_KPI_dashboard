"""
test_adaptador_supabase.py

Sin pytest: corre con `python -m parser.persistencia.test_adaptador_supabase`.

Cubre el roundtrip de VariableValue (incluyendo serie/trazabilidad/
etiqueta_fila, todo lo que vive en `detalle` JSONB), el UPSERT pisando
la fila anterior de la misma variable, respuestas_diagnostico, el
fail-closed de AdaptadorSupabase sin credenciales, y los seis métodos de
clínica/informe agregados para api-auth-onboarding-diagnostico
(crear_clinica, obtener_owner_id, marcar_migracion_completada,
esta_migracion_completada, cargar_informe, guardar_informe) — con un
fake del cliente de supabase-py, sin red.
"""

import os
import uuid
from types import SimpleNamespace

from parser.cobertura_calidad.coverage import VariableValue
from parser.cobertura_calidad.trazabilidad import Trazabilidad
from parser.persistencia.adaptador_supabase import AdaptadorSupabase


class _TablaFalsa:
    """Fake de la tabla de supabase-py: soporta las cadenas que usa
    AdaptadorSupabase — select().eq().execute() para leer,
    upsert(filas, on_conflict=...).execute() para escribir respetando la
    unique constraint (clinica_id, <clave>) como lo haría Postgres,
    insert(fila_o_filas).execute() generando `id` si no viene (como el
    `default gen_random_uuid()` de Postgres), y
    update(valores).eq(...).execute() aplicando solo a las filas que
    matchean los filtros acumulados."""

    def __init__(self, filas_por_tabla: dict, nombre: str):
        self._filas_por_tabla = filas_por_tabla
        self._nombre = nombre
        self._filtros: list[tuple[str, object]] = []
        self._pendiente_upsert = None
        self._pendiente_insert = None
        self._pendiente_update = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, columna, valor):
        self._filtros.append((columna, valor))
        return self

    def upsert(self, filas, on_conflict=None):
        self._pendiente_upsert = (filas, on_conflict)
        return self

    def insert(self, filas):
        self._pendiente_insert = filas
        return self

    def update(self, valores):
        self._pendiente_update = valores
        return self

    def execute(self):
        if self._pendiente_upsert is not None:
            filas_nuevas, on_conflict = self._pendiente_upsert
            claves = (on_conflict or "").split(",")
            existentes = self._filas_por_tabla.setdefault(self._nombre, [])
            for fila_nueva in filas_nuevas:
                idx = next(
                    (i for i, f in enumerate(existentes) if all(f.get(c) == fila_nueva.get(c) for c in claves)),
                    None,
                )
                if idx is not None:
                    existentes[idx] = fila_nueva
                else:
                    existentes.append(fila_nueva)
            return SimpleNamespace(data=filas_nuevas)

        if self._pendiente_insert is not None:
            filas_nuevas = self._pendiente_insert
            if isinstance(filas_nuevas, dict):
                filas_nuevas = [filas_nuevas]
            existentes = self._filas_por_tabla.setdefault(self._nombre, [])
            insertadas = []
            for fila_nueva in filas_nuevas:
                fila = dict(fila_nueva)
                fila.setdefault("id", str(uuid.uuid4()))
                existentes.append(fila)
                insertadas.append(fila)
            return SimpleNamespace(data=insertadas)

        if self._pendiente_update is not None:
            existentes = self._filas_por_tabla.get(self._nombre, [])
            actualizadas = []
            for fila in existentes:
                if all(fila.get(columna) == valor for columna, valor in self._filtros):
                    fila.update(self._pendiente_update)
                    actualizadas.append(fila)
            return SimpleNamespace(data=actualizadas)

        filas = list(self._filas_por_tabla.get(self._nombre, []))
        for columna, valor in self._filtros:
            filas = [f for f in filas if f.get(columna) == valor]
        return SimpleNamespace(data=filas)


class _ClienteSupabaseFalso:
    def __init__(self):
        self.filas_por_tabla: dict[str, list] = {}

    def table(self, nombre):
        return _TablaFalsa(self.filas_por_tabla, nombre)


def test_guardar_y_cargar_variables_hace_roundtrip_de_todos_los_campos():
    # El campo más fácil de romper en un roundtrip por JSONB: trazabilidad
    # (dataclass anidado) y serie (dict) tienen que sobrevivir intactos.
    traza = Trazabilidad(origen="celda", hoja="Resumen", columna="B", n_registros=3, unidad_final="ARS")
    vv = VariableValue(
        valor=16,
        fuente="migracion_excel",
        confianza=0.9,
        archivo_origen="clinica.xlsx",
        serie={"2026-04": 12, "2026-05": 16},
        periodo="2026-05",
        etiquetas_originales={"2026-05": "Mayo 2026"},
        trazabilidad=traza,
        etiqueta_fila=None,
    )
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    adaptador.guardar_variables("clinica-1", {"no_shows": vv})

    cargadas = adaptador.cargar_variables("clinica-1")

    assert cargadas == {"no_shows": vv}


def test_guardar_y_cargar_variable_tipo_dict_no_manda_un_dict_a_la_columna_numerica():
    # Bug real de producción: variables tipo "dict" de VARIABLE_TYPES (ej.
    # horas_tarea_manual_semana) traen un desglose {"total": 21.0} en
    # `.valor`. La columna `valor` de Postgres es `double precision` — si
    # el dict va directo ahí, Postgres rechaza el INSERT/UPSERT entero.
    vv = VariableValue(valor={"total": 21.0}, fuente="migracion_excel", confianza=0.8)
    cliente = _ClienteSupabaseFalso()
    adaptador = AdaptadorSupabase(cliente=cliente)

    adaptador.guardar_variables("clinica-1", {"horas_tarea_manual_semana": vv})

    fila_guardada = cliente.filas_por_tabla["variables"][0]
    assert fila_guardada["valor"] is None, "la columna numérica no debe recibir un dict"
    assert fila_guardada["detalle"]["valor"] == {"total": 21.0}

    cargadas = adaptador.cargar_variables("clinica-1")
    assert cargadas["horas_tarea_manual_semana"] == vv


def test_guardar_variables_upsert_pisa_el_valor_anterior_de_la_misma_variable():
    cliente = _ClienteSupabaseFalso()
    adaptador = AdaptadorSupabase(cliente=cliente)
    adaptador.guardar_variables("clinica-1", {"no_shows": VariableValue(10, "wizard")})
    adaptador.guardar_variables("clinica-1", {"no_shows": VariableValue(16, "migracion_excel")})

    cargadas = adaptador.cargar_variables("clinica-1")

    assert len(cliente.filas_por_tabla["variables"]) == 1, "el UPSERT no debe duplicar filas"
    assert cargadas["no_shows"].valor == 16
    assert cargadas["no_shows"].fuente == "migracion_excel"


def test_cargar_variables_no_mezcla_clinicas_distintas():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    adaptador.guardar_variables("clinica-1", {"no_shows": VariableValue(16, "migracion_excel")})
    adaptador.guardar_variables("clinica-2", {"no_shows": VariableValue(99, "migracion_excel")})

    assert adaptador.cargar_variables("clinica-1")["no_shows"].valor == 16
    assert adaptador.cargar_variables("clinica-2")["no_shows"].valor == 99


def test_cargar_variables_de_clinica_sin_datos_devuelve_dict_vacio():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    assert adaptador.cargar_variables("clinica-inexistente") == {}


def test_guardar_variables_con_dict_vacio_no_llama_al_cliente():
    class _ClienteQueNuncaDeberiaLlamarse:
        def table(self, nombre):
            raise AssertionError("no debería llamarse con variables={}")

    adaptador = AdaptadorSupabase(cliente=_ClienteQueNuncaDeberiaLlamarse())
    adaptador.guardar_variables("clinica-1", {})  # no debe lanzar


def test_respuestas_diagnostico_hace_roundtrip_y_upsert_pisa_la_anterior():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    adaptador.guardar_respuestas_diagnostico("clinica-1", {"P2": "a mano"})
    adaptador.guardar_respuestas_diagnostico("clinica-1", {"P2": "recordatorio automático"})

    respuestas = adaptador.cargar_respuestas_diagnostico("clinica-1")

    assert respuestas == {"P2": "recordatorio automático"}


def test_adaptador_supabase_sin_credenciales_falla_cerrado():
    previo_url = os.environ.pop("SUPABASE_URL", None)
    previo_key = os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
    try:
        fallo = False
        try:
            AdaptadorSupabase()
        except RuntimeError as error:
            fallo = True
            assert "SUPABASE_URL" in str(error)
        assert fallo, "sin credenciales de Supabase tiene que fallar cerrado, no intentar conectar"
    finally:
        if previo_url is not None:
            os.environ["SUPABASE_URL"] = previo_url
        if previo_key is not None:
            os.environ["SUPABASE_SERVICE_ROLE_KEY"] = previo_key


def test_crear_clinica_devuelve_el_id_generado():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    clinica_id = adaptador.crear_clinica("Clínica Sonrisas", owner_id="owner-1")

    assert isinstance(clinica_id, str) and clinica_id, "crear_clinica debe devolver un id no vacío"


def test_obtener_owner_id_devuelve_el_owner_de_la_clinica_creada():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    clinica_id = adaptador.crear_clinica("Clínica Sonrisas", owner_id="owner-1")

    assert adaptador.obtener_owner_id(clinica_id) == "owner-1"


def test_obtener_owner_id_de_clinica_inexistente_devuelve_none():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    assert adaptador.obtener_owner_id(str(uuid.uuid4())) is None


def test_esta_migracion_completada_es_false_hasta_marcarla():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    clinica_id = adaptador.crear_clinica("Clínica Sonrisas", owner_id="owner-1")

    assert adaptador.esta_migracion_completada(clinica_id) is False

    adaptador.marcar_migracion_completada(clinica_id)

    assert adaptador.esta_migracion_completada(clinica_id) is True


def test_esta_migracion_completada_de_clinica_inexistente_devuelve_false():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    assert adaptador.esta_migracion_completada(str(uuid.uuid4())) is False


def test_cargar_informe_de_clinica_sin_informe_devuelve_none():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    clinica_id = adaptador.crear_clinica("Clínica Sonrisas", owner_id="owner-1")

    assert adaptador.cargar_informe(clinica_id) is None


def test_guardar_y_cargar_informe_hace_roundtrip():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    clinica_id = adaptador.crear_clinica("Clínica Sonrisas", owner_id="owner-1")

    adaptador.guardar_informe(clinica_id, "Informe narrativo generado por Opus.")

    assert adaptador.cargar_informe(clinica_id) == "Informe narrativo generado por Opus."


def test_guardar_informe_dos_veces_pisa_el_texto_anterior_sin_duplicar_fila():
    cliente = _ClienteSupabaseFalso()
    adaptador = AdaptadorSupabase(cliente=cliente)
    clinica_id = adaptador.crear_clinica("Clínica Sonrisas", owner_id="owner-1")

    adaptador.guardar_informe(clinica_id, "Primera versión.")
    adaptador.guardar_informe(clinica_id, "Segunda versión, regenerada.")

    assert len(cliente.filas_por_tabla["informes"]) == 1, "guardar_informe no debe duplicar filas por clínica"
    assert adaptador.cargar_informe(clinica_id) == "Segunda versión, regenerada."


def test_obtener_respuesta_idempotente_sin_clave_guardada_devuelve_none():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    assert adaptador.obtener_respuesta_idempotente("clave-1", owner_id="owner-1") is None


def test_guardar_y_obtener_respuesta_idempotente_hace_roundtrip():
    adaptador = AdaptadorSupabase(cliente=_ClienteSupabaseFalso())
    respuesta = {"id": "clinica-1", "nombre": "Clínica Sonrisas", "owner_id": "owner-1"}

    adaptador.guardar_respuesta_idempotente("clave-1", owner_id="owner-1", respuesta=respuesta)

    assert adaptador.obtener_respuesta_idempotente("clave-1", owner_id="owner-1") == respuesta


def test_obtener_respuesta_idempotente_no_mezcla_owners_con_la_misma_clave():
    cliente = _ClienteSupabaseFalso()
    adaptador = AdaptadorSupabase(cliente=cliente)
    adaptador.guardar_respuesta_idempotente("clave-1", owner_id="owner-1", respuesta={"nombre": "De owner-1"})

    assert adaptador.obtener_respuesta_idempotente("clave-1", owner_id="owner-2") is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
