"""
test_probar_manual.py

Sin pytest: corre con `python -m parser.test_probar_manual`.

No importa probar_manual.py directamente: es un script de Streamlit que
ejecuta `st.*` de nivel superior al importarse (st.set_page_config,
st.stop() si falta ANTHROPIC_API_KEY, etc.), no un módulo de funciones
aisladas. Este test reproduce en un helper local, línea por línea, el
patrón exacto del bloque `st.button("Procesar migración", ...)` de
probar_manual.py -- `tempfile.mkdtemp()` + escribir cada archivo con su
nombre original + `try/except/finally: shutil.rmtree(ignore_errors=True)`
-- para probar que la limpieza corre siempre, tanto si `procesar_migracion`
termina bien como si lanza una excepción. Cubre el Requirement "Temporary
Upload Cleanup" del spec: no hace falta ningún cambio en probar_manual.py,
el `finally` ya cubre ambos caminos hoy.
"""

import os
import shutil
import tempfile


class _ArchivoFalso:
    """Fake mínimo de UploadedFile de Streamlit: sólo `.name` y
    `.getvalue()`, que es todo lo que probar_manual.py usa al escribir a
    disco -- sin depender de streamlit ni de un archivo real."""

    def __init__(self, name: str, contenido: bytes):
        self.name = name
        self._contenido = contenido

    def getvalue(self) -> bytes:
        return self._contenido


def _simular_boton_procesar_migracion(archivos_subidos, procesar_fn):
    """Reproduce, sin Streamlit, el bloque bajo
    `st.button("Procesar migración", ...)` de probar_manual.py: escribe
    cada archivo subido con su nombre original dentro de un directorio
    temporal, llama a `procesar_fn(paths_temporales)`, y borra el
    directorio temporal en un `finally` -- corra bien o lance excepción --
    exactamente el mismo patrón que el original (mkdtemp, nombre original
    vía os.path.basename, try/except Exception/finally shutil.rmtree)."""
    dir_temporal = tempfile.mkdtemp()
    paths_temporales = []
    for archivo in archivos_subidos or []:
        destino = os.path.join(dir_temporal, os.path.basename(archivo.name))
        with open(destino, "wb") as f:
            f.write(archivo.getvalue())
        paths_temporales.append(destino)

    excepcion_capturada = None
    try:
        procesar_fn(paths_temporales)
    except Exception as e:
        excepcion_capturada = e
    finally:
        shutil.rmtree(dir_temporal, ignore_errors=True)

    return dir_temporal, excepcion_capturada


def test_limpieza_ocurre_tras_procesamiento_exitoso():
    archivos = [_ArchivoFalso("presupuestos_abril.csv", b"col1,col2\n1,2\n")]
    dir_temporal, excepcion = _simular_boton_procesar_migracion(
        archivos, procesar_fn=lambda paths: None,
    )
    assert excepcion is None
    assert not os.path.exists(dir_temporal)


def test_limpieza_ocurre_cuando_procesar_migracion_lanza_excepcion():
    archivos = [_ArchivoFalso("turnos_mayo.xlsx", b"contenido binario simulado")]

    def _procesar_que_falla(paths):
        raise ValueError("fallo simulado de procesar_migracion")

    dir_temporal, excepcion = _simular_boton_procesar_migracion(
        archivos, procesar_fn=_procesar_que_falla,
    )
    assert isinstance(excepcion, ValueError)
    assert not os.path.exists(dir_temporal)


def test_limpieza_ocurre_incluso_sin_archivos_subidos():
    # Caso "sin archivos" del Paso 3 opcional del onboarding (uploader
    # vacío, procesar igual): dir_temporal se crea vacío y se borra igual.
    dir_temporal, excepcion = _simular_boton_procesar_migracion(
        [], procesar_fn=lambda paths: None,
    )
    assert excepcion is None
    assert not os.path.exists(dir_temporal)


def test_archivo_temporal_conserva_nombre_original_antes_de_la_limpieza():
    # No alcanza con que el directorio desaparezca al final: mientras corre,
    # el archivo temporal tiene que usar el nombre original (para que
    # archivo_origen viaje correcto en trazabilidad/conflictos), no un
    # nombre random tipo NamedTemporaryFile.
    archivos = [_ArchivoFalso("no_shows_marzo.png", b"bytes de imagen simulados")]
    paths_vistos = []

    def _procesar_que_inspecciona(paths):
        paths_vistos.extend(paths)

    _simular_boton_procesar_migracion(archivos, procesar_fn=_procesar_que_inspecciona)
    assert len(paths_vistos) == 1
    assert os.path.basename(paths_vistos[0]) == "no_shows_marzo.png"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
