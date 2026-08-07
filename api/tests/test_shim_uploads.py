"""
test_shim_uploads.py

Roundtrip del shim `ArchivoSubidoShim`/`envolver_upload_file`/
`envolver_uploads` sobre `fastapi.UploadFile`: confirma que `.name` y
`.getvalue()` exponen exactamente el filename y los bytes originales
(el contrato que `parser/archivos_temporales.py::escribir_temporales`
espera), sin tocar red ni Supabase.
"""

import io

from fastapi import UploadFile

from api.shim_uploads import envolver_upload_file, envolver_uploads


def test_envolver_upload_file_expone_name_y_getvalue():
    archivo = UploadFile(file=io.BytesIO(b"contenido binario"), filename="clinica.xlsx")

    shim = envolver_upload_file(archivo)

    assert shim.name == "clinica.xlsx"
    assert shim.getvalue() == b"contenido binario"


def test_envolver_upload_file_sin_filename_usa_default_archivo():
    archivo = UploadFile(file=io.BytesIO(b"x"), filename=None)

    shim = envolver_upload_file(archivo)

    assert shim.name == "archivo"


def test_envolver_uploads_envuelve_una_lista_preservando_orden():
    archivos = [
        UploadFile(file=io.BytesIO(b"contenido a"), filename="a.pdf"),
        UploadFile(file=io.BytesIO(b"contenido b"), filename="b.png"),
    ]

    shims = envolver_uploads(archivos)

    assert [s.name for s in shims] == ["a.pdf", "b.png"]
    assert [s.getvalue() for s in shims] == [b"contenido a", b"contenido b"]


def test_envolver_uploads_con_lista_vacia_devuelve_lista_vacia():
    assert envolver_uploads([]) == []
