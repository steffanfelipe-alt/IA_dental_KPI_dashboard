"""
archivos_temporales.py

Context manager chico para escribir archivos subidos a un directorio
temporal (con su nombre ORIGINAL, no un nombre random — así
`archivo_origen` viaja legible por trazabilidad/conflictos) y limpiarlo
siempre al salir del `with`, corra bien o lance excepción.

Separado de probar_manual.py a propósito, no como un helper adentro de
ese archivo: probar_manual.py ejecuta `st.*` de nivel superior al
importarse (st.set_page_config, st.stop() si falta ANTHROPIC_API_KEY),
así que nada de ese archivo se puede importar en un test standalone sin
un runtime real de Streamlit. Este módulo no importa streamlit, así que
sí se puede probar directo — ver test_archivos_temporales.py.
"""

import os
import shutil
import tempfile
from contextlib import contextmanager


@contextmanager
def escribir_temporales(archivos_subidos):
    """
    Escribe cada archivo subido (objetos con `.name` y `.getvalue()`,
    contrato de UploadedFile de Streamlit) a un directorio temporal nuevo,
    usando su nombre original vía `os.path.basename`. Devuelve la lista de
    paths escritos. Al salir del `with` (éxito o excepción) borra el
    directorio temporal completo.
    """
    dir_temporal = tempfile.mkdtemp()
    try:
        paths_temporales = []
        for archivo in archivos_subidos or []:
            destino = os.path.join(dir_temporal, os.path.basename(archivo.name))
            with open(destino, "wb") as f:
                f.write(archivo.getvalue())
            paths_temporales.append(destino)
        yield paths_temporales
    finally:
        shutil.rmtree(dir_temporal, ignore_errors=True)
