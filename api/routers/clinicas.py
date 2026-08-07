"""
routers/clinicas.py

`POST /clinicas`: alta de clínica con `owner_id` fijado al usuario
autenticado (`CurrentUserDep.id`), nunca al valor del body — un usuario
autenticado sólo puede crear una clínica de la que él es owner (spec:
"owner_id = auth.uid()").

`GET /clinicas/{id}/diagnostico`: recompute determinista (sin LLM) del
diagnóstico estructurado — `procesar_migracion(archivos=[], ...)` con
lo ya persistido (`variables`/`respuestas_diagnostico`), no una
migración nueva. 409 si el onboarding no está completo (mismo gate que
`GET /onboarding/{id}/estado`, ver `api/onboarding_estado.py`).

`POST /clinicas/{id}/informe`: generate-once. Si `cargar_informe` ya
tiene algo guardado, lo devuelve tal cual — NUNCA vuelve a llamar a
Opus. Si no, corre el mismo `procesar_migracion` que el diagnóstico
para tener el input estructurado, y recién ahí llama a
`interpretar_clinica` (el único LLM call de este PR) y persiste el
resultado antes de devolverlo.

`GET /clinicas/{id}/informe`: sólo lee lo persistido, 404 si nunca se
generó.

`procesar_migracion`/`interpretar_clinica` se importan por nombre a
este módulo (mismo criterio que `procesar_migracion`/`resolver_conflicto`
en `onboarding.py`) para que los tests puedan monkeypatchearlos directo
en el boundary de import de este router
(`api.routers.clinicas.procesar_migracion`, etc.) sin necesitar un
`Depends` — son llamadas a funciones de dominio, no a infraestructura
inyectable.
"""

from fastapi import APIRouter, HTTPException, status

from api.deps import ClienteAnthropicDep, CurrentUserDep, OwnerDeClinicaDep, RepositorioDep
from api.onboarding_estado import exigir_onboarding_completo
from api.schemas.clinicas import ClinicaResponse, CrearClinicaRequest
from api.schemas.diagnostico_informe import DiagnosticoResponse, InformeResponse
from parser.diagnostico.guia_diagnostico import PREGUNTAS_REQUERIDAS_ONBOARDING
from parser.interpretacion.interpretacion import interpretar_clinica
from parser.pipeline import procesar_migracion

router = APIRouter(prefix="/clinicas", tags=["clinicas"])


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_clinica(
    datos: CrearClinicaRequest,
    usuario_actual: CurrentUserDep,
    repo: RepositorioDep,
) -> ClinicaResponse:
    clinica_id = repo.crear_clinica(datos.nombre, owner_id=usuario_actual.id)
    return ClinicaResponse(id=clinica_id, nombre=datos.nombre, owner_id=usuario_actual.id)


@router.get("/{clinica_id}/diagnostico")
def obtener_diagnostico(clinica_id: OwnerDeClinicaDep, repo: RepositorioDep) -> DiagnosticoResponse:
    exigir_onboarding_completo(clinica_id, repo, PREGUNTAS_REQUERIDAS_ONBOARDING)
    resultado = procesar_migracion(
        archivos=[],
        variables_previas=repo.cargar_variables(clinica_id),
        respuestas_diagnostico=repo.cargar_respuestas_diagnostico(clinica_id),
    )
    return DiagnosticoResponse(diagnostico=resultado["diagnostico"])


@router.post("/{clinica_id}/informe")
def generar_informe(
    clinica_id: OwnerDeClinicaDep,
    repo: RepositorioDep,
    cliente_llm: ClienteAnthropicDep,
) -> InformeResponse:
    # Generate-once: si ya hay uno guardado, se devuelve tal cual — el
    # gate de completitud y `procesar_migracion`/`interpretar_clinica`
    # NUNCA corren en un repeat request (ver spec: "Repeat generation ...
    # with no new Opus call").
    existente = repo.cargar_informe(clinica_id)
    if existente is not None:
        return InformeResponse(texto=existente)

    exigir_onboarding_completo(clinica_id, repo, PREGUNTAS_REQUERIDAS_ONBOARDING)
    respuestas_diagnostico = repo.cargar_respuestas_diagnostico(clinica_id)
    resultado = procesar_migracion(
        archivos=[],
        variables_previas=repo.cargar_variables(clinica_id),
        respuestas_diagnostico=respuestas_diagnostico,
    )
    respuesta = interpretar_clinica(
        diagnosticos=resultado["diagnostico"],
        oportunidades_priorizadas=resultado["oportunidades_priorizadas"],
        calidad_datos=resultado["calidad_datos"],
        respuestas_diagnostico=respuestas_diagnostico,
        variables_en_cuarentena=resultado["variables_en_cuarentena"],
        discrepancias_reconciliacion=resultado["discrepancias_reconciliacion"],
        variables_derivadas=resultado["variables_derivadas"],
        conflictos_pendientes=resultado["conflictos_pendientes"],
        client=cliente_llm,
    )
    texto = respuesta["informe"]
    repo.guardar_informe(clinica_id, texto)
    return InformeResponse(texto=texto)


@router.get("/{clinica_id}/informe")
def obtener_informe(clinica_id: OwnerDeClinicaDep, repo: RepositorioDep) -> InformeResponse:
    texto = repo.cargar_informe(clinica_id)
    if texto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Todavía no se generó un informe para esta clínica.")
    return InformeResponse(texto=texto)
