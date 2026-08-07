"""
schemas/clinicas.py

Pydantic wrappers para `POST /clinicas`. `owner_id` en `ClinicaResponse`
siempre es el id del usuario autenticado que hizo la request — nunca un
valor que venga del body (ver `api/routers/clinicas.py`, el `owner_id`
sale de `CurrentUserDep`, no de `CrearClinicaRequest`).
"""

from pydantic import BaseModel


class CrearClinicaRequest(BaseModel):
    nombre: str


class ClinicaResponse(BaseModel):
    id: str
    nombre: str
    owner_id: str
