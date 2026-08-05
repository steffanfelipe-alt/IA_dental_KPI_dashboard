"""
test_probar_manual.py

Sin pytest: corre con `python -m parser.test_probar_manual`.

No prueba probar_manual.py directamente: es un script de Streamlit que
ejecuta `st.*` de nivel superior al importarse (st.set_page_config,
st.stop() si falta ANTHROPIC_API_KEY), así que no se puede importar en un
runner standalone. Por eso probar_manual.py delega la escritura/limpieza
de temporales a `parser.archivos_temporales.escribir_temporales` — un
módulo separado, sin dependencia de streamlit, que SÍ se puede importar y
probar directo acá. Este archivo prueba ese módulo real (el mismo que usa
probar_manual.py en producción), no una copia de su lógica.
"""

import os

from parser.archivos_temporales import escribir_temporales


class _ArchivoFalso:
    """Fake mínimo de UploadedFile de Streamlit: sólo `.name` y
    `.getvalue()`, que es todo lo que escribir_temporales necesita."""

    def __init__(self, name: str, contenido: bytes):
        self.name = name
        self._contenido = contenido

    def getvalue(self) -> bytes:
        return self._contenido


def test_limpieza_ocurre_tras_procesamiento_exitoso():
    archivos = [_ArchivoFalso("presupuestos_abril.csv", b"col1,col2\n1,2\n")]
    with escribir_temporales(archivos) as paths_temporales:
        dir_temporal = os.path.dirname(paths_temporales[0])
        assert os.path.exists(dir_temporal)
    assert not os.path.exists(dir_temporal)


def test_limpieza_ocurre_cuando_el_procesamiento_lanza_excepcion():
    archivos = [_ArchivoFalso("turnos_mayo.xlsx", b"contenido binario simulado")]
    dir_temporal = None
    excepcion_capturada = None
    try:
        with escribir_temporales(archivos) as paths_temporales:
            dir_temporal = os.path.dirname(paths_temporales[0])
            raise ValueError("fallo simulado de procesar_migracion")
    except ValueError as e:
        excepcion_capturada = e
    assert isinstance(excepcion_capturada, ValueError)
    assert not os.path.exists(dir_temporal)


def test_limpieza_ocurre_incluso_sin_archivos_subidos():
    # Caso "sin archivos" del Paso 3 opcional del onboarding (uploader
    # vacío, procesar igual): el directorio se crea vacío y no explota al
    # salir del `with`, aunque no haya ningún path que devolver.
    with escribir_temporales([]) as paths_temporales:
        assert paths_temporales == []


def test_archivo_temporal_conserva_nombre_original_antes_de_la_limpieza():
    # No alcanza con que el directorio desaparezca al final: mientras corre,
    # el archivo temporal tiene que usar el nombre original (para que
    # archivo_origen viaje correcto en trazabilidad/conflictos), no un
    # nombre random tipo NamedTemporaryFile.
    archivos = [_ArchivoFalso("no_shows_marzo.png", b"bytes de imagen simulados")]
    with escribir_temporales(archivos) as paths_temporales:
        assert len(paths_temporales) == 1
        assert os.path.basename(paths_temporales[0]) == "no_shows_marzo.png"
        assert os.path.exists(paths_temporales[0])


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
