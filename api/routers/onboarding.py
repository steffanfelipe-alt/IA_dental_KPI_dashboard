"""
routers/onboarding.py

Cinco rutas, todas gateadas por `OwnerDeClinicaDep` (guard de ownership,
ver `api/deps.py`):

  POST /onboarding/{id}/migrar             — sube archivo(s), corre
                                              `procesar_migracion`
                                              síncrono, guarda variables
                                              y marca la migración
                                              completada.
  POST /onboarding/{id}/resolver-conflicto — aplica la elección del
                                              dueño sobre un conflicto
                                              pendiente y re-guarda
                                              variables.
  GET  /onboarding/{id}/guia               — catálogo de preguntas
                                              requeridas + lo ya
                                              contestado.
  PUT  /onboarding/{id}/respuestas         — guarda/actualiza
                                              respuestas de la Guía.
  GET  /onboarding/{id}/estado             — gate de completitud del
                                              onboarding (ver
                                              `EstadoResponse`).

Todas `def` síncronas — mismo criterio que el resto de las rutas que
llaman a `parser/` (ver design: ninguna ruta que invoca `parser/` es
`async def`; corren en threadpool).

`procesar_migracion`/`resolver_conflicto`/`escribir_temporales` se
importan por nombre a este módulo (no `from parser import pipeline` +
`pipeline.procesar_migracion(...)`) para que los tests puedan
monkeypatchearlos directo en el boundary de import de este router
(`api.routers.onboarding.procesar_migracion`, etc.) sin necesitar un
`Depends` — son llamadas a funciones de dominio, no a infraestructura
inyectable como el repositorio.
"""

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from api.config import EXTENSIONES_PERMITIDAS, TAMANO_MAXIMO_ARCHIVO_BYTES
from api.deps import OwnerDeClinicaDep, RepositorioDep
from api.onboarding_estado import calcular_estado_onboarding
from api.schemas.onboarding import (
    EstadoResponse,
    GuiaResponse,
    PreguntaGuiaResponse,
    ResolverConflictoRequest,
    RespuestasRequest,
)
from api.shim_uploads import envolver_uploads
from parser.archivos_temporales import escribir_temporales
from parser.cobertura_calidad.preguntas_wizard import preguntas_cubiertas_por_variables
from parser.diagnostico.guia_diagnostico import PREGUNTAS_REQUERIDAS_ONBOARDING
from parser.pipeline import procesar_migracion, resolver_conflicto

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _validar_archivos(archivos: list[UploadFile]) -> None:
    """413 si algún archivo excede `TAMANO_MAXIMO_ARCHIVO_BYTES`, 415 si
    su extensión no está en `EXTENSIONES_PERMITIDAS`. Usa
    `seek`/`tell`/`seek(0)` en vez de leer y descartar: el shim
    (`envolver_uploads`) todavía necesita leer estos mismos archivos
    después, y `UploadFile.file` es un `SpooledTemporaryFile` posicional
    — un `.read()` acá sin rebobinar dejaría el archivo vacío para el
    shim."""
    for archivo in archivos:
        extension = Path(archivo.filename or "").suffix.lower()
        if extension not in EXTENSIONES_PERMITIDAS:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                f"Extensión no soportada: '{extension or '(sin extensión)'}' "
                f"(archivo: {archivo.filename}).",
            )
        archivo.file.seek(0, os.SEEK_END)
        tamano = archivo.file.tell()
        archivo.file.seek(0)
        if tamano > TAMANO_MAXIMO_ARCHIVO_BYTES:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"Archivo demasiado grande: {archivo.filename} ({tamano} bytes, "
                f"máximo {TAMANO_MAXIMO_ARCHIVO_BYTES} bytes).",
            )


@router.post("/{clinica_id}/migrar")
def migrar(
    clinica_id: OwnerDeClinicaDep,
    repo: RepositorioDep,
    archivos: list[UploadFile] = File(...),
) -> dict[str, Any]:
    _validar_archivos(archivos)

    variables_previas = repo.cargar_variables(clinica_id)
    archivos_shim = envolver_uploads(archivos)
    with escribir_temporales(archivos_shim) as paths:
        resultado = procesar_migracion(archivos=paths, variables_previas=variables_previas)

    repo.guardar_variables(clinica_id, resultado["variables"])
    # "Éxito" acá es "procesar_migracion no reventó" — un archivo
    # ilegible individual ya cae en resultado["archivos_fallidos"] sin
    # levantar excepción (ver docstring de procesar_migracion), así que
    # llegar a esta línea siempre significa que el upload se procesó.
    repo.marcar_migracion_completada(clinica_id)
    return resultado


@router.post("/{clinica_id}/resolver-conflicto")
def resolver_conflicto_de_variable(
    clinica_id: OwnerDeClinicaDep,
    datos: ResolverConflictoRequest,
    repo: RepositorioDep,
) -> dict[str, Any]:
    variables_previas = repo.cargar_variables(clinica_id)
    resultado = resolver_conflicto(
        variable=datos.variable,
        variables_previas=variables_previas,
        valor=datos.valor,
        valor_manual=datos.valor_manual,
        respuestas_diagnostico=datos.respuestas_diagnostico,
        candidatos=datos.candidatos,
        periodos_de_escalares=datos.periodos_de_escalares,
    )
    repo.guardar_variables(clinica_id, resultado["variables"])
    return resultado


@router.get("/{clinica_id}/guia")
def obtener_guia(clinica_id: OwnerDeClinicaDep, repo: RepositorioDep) -> GuiaResponse:
    # Design "Filter the catalog server-side in /guia" (change
    # veredicto-wizard-usability-fixes): una pregunta cuantitativa del
    # catálogo se omite cuando TODAS las variables de wizard que la
    # respaldan ya están en `variables` (extraídas por una migración
    # previa) — recalculado en cada GET, nunca cacheado desde /migrar.
    respuestas = repo.cargar_respuestas_diagnostico(clinica_id)
    preguntas_cubiertas = frozenset(preguntas_cubiertas_por_variables(repo.cargar_variables(clinica_id)))
    preguntas = [
        PreguntaGuiaResponse(
            id=pregunta.id,
            texto=pregunta.texto,
            bloque=pregunta.bloque,
            nombre_bloque=pregunta.nombre_bloque,
            nucleo=pregunta.nucleo,
            respuesta=respuestas.get(pregunta.id),
        )
        for pregunta in PREGUNTAS_REQUERIDAS_ONBOARDING.values()
        if pregunta.id not in preguntas_cubiertas
    ]
    return GuiaResponse(preguntas=preguntas)


@router.put("/{clinica_id}/respuestas", status_code=status.HTTP_204_NO_CONTENT)
def guardar_respuestas(clinica_id: OwnerDeClinicaDep, datos: RespuestasRequest, repo: RepositorioDep) -> None:
    repo.guardar_respuestas_diagnostico(clinica_id, datos.respuestas)


@router.get("/{clinica_id}/estado")
def obtener_estado(clinica_id: OwnerDeClinicaDep, repo: RepositorioDep) -> EstadoResponse:
    # Fase PR4: la cuenta de "qué falta" se factoreó a
    # api.onboarding_estado.calcular_estado_onboarding, que también usan
    # GET /clinicas/{id}/diagnostico y POST|GET /clinicas/{id}/informe
    # como gate de 409 — misma condición de completitud, un solo lugar
    # que la calcula. PREGUNTAS_REQUERIDAS_ONBOARDING se sigue leyendo
    # del nombre a nivel módulo de ESTE router (no importado dentro de
    # la función compartida) para que los tests existentes que
    # monkeypatchean `onboarding.PREGUNTAS_REQUERIDAS_ONBOARDING` sigan
    # funcionando sin cambios.
    #
    # `preguntas_cubiertas` (change veredicto-wizard-usability-fixes):
    # mismo cálculo que `obtener_guia` — si no se descontara acá, una
    # pregunta que /guia ya deja de pedir seguiría contando como
    # faltante y `completo` nunca llegaría a `true`.
    migracion_completada = repo.esta_migracion_completada(clinica_id)
    respuestas = repo.cargar_respuestas_diagnostico(clinica_id)
    preguntas_cubiertas = frozenset(preguntas_cubiertas_por_variables(repo.cargar_variables(clinica_id)))
    estado = calcular_estado_onboarding(
        migracion_completada, respuestas, PREGUNTAS_REQUERIDAS_ONBOARDING, preguntas_cubiertas
    )
    return EstadoResponse(
        completo=estado.completo,
        migracion_completada=estado.migracion_completada,
        preguntas_faltantes=estado.preguntas_faltantes,
    )
