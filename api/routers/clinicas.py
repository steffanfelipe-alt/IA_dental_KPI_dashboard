"""
routers/clinicas.py

`POST /clinicas`: alta de clínica con `owner_id` fijado al usuario
autenticado (`CurrentUserDep.id`), nunca al valor del body — un usuario
autenticado sólo puede crear una clínica de la que él es owner (spec:
"owner_id = auth.uid()").

`GET /clinicas/{id}/diagnostico` y `POST|GET /clinicas/{id}/informe`
(tasks 4.5/4.6) NO están en este router todavía — llegan en el PR de
diagnóstico/informe.
"""

from fastapi import APIRouter, status

from api.deps import CurrentUserDep, RepositorioDep
from api.schemas.clinicas import ClinicaResponse, CrearClinicaRequest

router = APIRouter(prefix="/clinicas", tags=["clinicas"])


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_clinica(
    datos: CrearClinicaRequest,
    usuario_actual: CurrentUserDep,
    repo: RepositorioDep,
) -> ClinicaResponse:
    clinica_id = repo.crear_clinica(datos.nombre, owner_id=usuario_actual.id)
    return ClinicaResponse(id=clinica_id, nombre=datos.nombre, owner_id=usuario_actual.id)
