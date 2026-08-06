"""
errores.py

Contrato de error uniforme para toda la API: cualquier `HTTPException`
levantada en un router/dependencia (401/403/404/409, y lo que venga)
y cualquier error de validación de Pydantic (422) llegan al cliente con
la misma forma de JSON:

    {"error": {"codigo": <int>, "mensaje": <str>, "detalle": <opcional>}}

Sin este handler, FastAPI devuelve `{"detail": ...}` para HTTPException y
una forma distinta para RequestValidationError — dos contratos diferentes
para el mismo tipo de cosa (un error). Centralizar acá evita que cada
router tenga que decidir la forma de su propia respuesta de error.
"""

from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _envolver_error(codigo: int, mensaje: str, detalle: Optional[Any] = None) -> dict:
    cuerpo: dict[str, Any] = {"error": {"codigo": codigo, "mensaje": mensaje}}
    if detalle is not None:
        cuerpo["error"]["detalle"] = detalle
    return cuerpo


async def _manejar_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_envolver_error(exc.status_code, str(exc.detail)))


async def _manejar_error_de_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_envolver_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Error de validación en la petición.",
            detalle=exc.errors(),
        ),
    )


def registrar_manejadores_de_error(app: FastAPI) -> None:
    """Registra los dos handlers globales. Cubre 401/403/404/409 (todos
    levantados como `HTTPException` por deps/routers) y 422 (validación
    de Pydantic) con el mismo contrato de respuesta."""
    app.add_exception_handler(StarletteHTTPException, _manejar_http_exception)
    app.add_exception_handler(RequestValidationError, _manejar_error_de_validacion)
