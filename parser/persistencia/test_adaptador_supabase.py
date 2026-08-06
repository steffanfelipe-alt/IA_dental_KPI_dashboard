"""
test_adaptador_supabase.py

Sin pytest: corre con `python -m parser.persistencia.test_adaptador_supabase`.

Cubre el roundtrip de VariableValue (incluyendo serie/trazabilidad/
etiqueta_fila, todo lo que vive en `detalle` JSONB), el UPSERT pisando
la fila anterior de la misma variable, respuestas_diagnostico, y el
fail-closed de AdaptadorSupabase sin credenciales — con un fake del
cliente de supabase-py, sin red.
"""

import os
from types import SimpleNamespace

from parser.cobertura_calidad.coverage import VariableValue
from parser.cobertura_calidad.trazabilidad import Trazabilidad
from parser.persistencia.adaptador_supabase import AdaptadorSupabase


class _TablaFalsa:
    """Fake de la tabla de supabase-py: soporta la única cadena que usa
    AdaptadorSupabase — select().eq().execute() para leer, y
    upsert(filas, on_conflict=...).execute() para escribir, respetando
    la unique constraint (clinica_id, <clave>) como lo haría Postgres."""

    def __init__(self, filas_por_tabla: dict, nombre: str):
        self._filas_por_tabla = filas_por_tabla
        self._nombre = nombre
        self._filtros: list[tuple[str, object]] = []
        self._pendiente_upsert = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, columna, valor):
        self._filtros.append((columna, valor))
        return self

    def upsert(self, filas, on_conflict=None):
        self._pendiente_upsert = (filas, on_conflict)
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


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
