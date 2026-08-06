"""
shim_uploads.py

`parser/archivos_temporales.py::escribir_temporales` espera objetos con
`.name` y `.getvalue()` (el contrato de `UploadedFile` de Streamlit).
`fastapi.UploadFile` no tiene esa forma (`.filename` y `.file.read()` /
`await .read()`). En vez de tocar `archivos_temporales.py` para que
conozca dos contratos distintos de "archivo subido" (decisión de
design: mantener ese helper con el contrato de Streamlit intacto), este
módulo envuelve cada `UploadFile` en un objeto chico que sí cumple el
contrato — el shim vive en el borde (`api/`, el adapter que entra desde
HTTP), no en el dominio.

Lectura síncrona (`archivo.file.read()`, no `await archivo.read()`)
a propósito: el router que va a usar esto es `def` síncrono (corre en
threadpool), no `async def` — mismo criterio que el resto de las rutas
que llaman a `parser/` (ver design: ninguna ruta que llama a `parser/`
es `async def`).
"""

from dataclasses import dataclass

from fastapi import UploadFile


@dataclass(frozen=True)
class ArchivoSubidoShim:
    """Envoltorio mínimo que expone `.name`/`.getvalue()` sobre los bytes
    ya leídos de un `UploadFile`."""

    name: str
    contenido: bytes

    def getvalue(self) -> bytes:
        return self.contenido


def envolver_upload_file(archivo: UploadFile) -> ArchivoSubidoShim:
    contenido = archivo.file.read()
    return ArchivoSubidoShim(name=archivo.filename or "archivo", contenido=contenido)


def envolver_uploads(archivos: list[UploadFile]) -> list[ArchivoSubidoShim]:
    return [envolver_upload_file(archivo) for archivo in archivos]
