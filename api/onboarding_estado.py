"""
onboarding_estado.py

Completitud del onboarding: "migración procesada" AND "todas las
`PREGUNTAS_REQUERIDAS_ONBOARDING` contestadas" — la misma condición que
`GET /onboarding/{id}/estado` expone (ver `api/routers/onboarding.py`,
`api/schemas/onboarding.py::EstadoResponse`) y que `GET
/clinicas/{id}/diagnostico` y `POST|GET /clinicas/{id}/informe` usan
como gate de 409 (design del cambio: "409 if onboarding isn't complete
(same completeness check as GET /onboarding/{id}/estado)").

Vive en un módulo propio, no en `api/deps.py`, porque no es una
dependencia de FastAPI: no gatea una ruta con un guard de auth/ownership
inyectado vía `Depends` como `CurrentUserDep`/`OwnerDeClinicaDep` —
es una función de dominio de la API pura (sin `Depends`) que dos
routers distintos (`onboarding.py` y `clinicas.py`) necesitan llamar
por nombre. Meterla en `deps.py` hubiera mezclado dos tipos de cosas
distintas (guards inyectables vs. lógica de negocio de la API) bajo el
mismo módulo.

`calcular_estado_onboarding` recibe `preguntas_requeridas` como
parámetro en vez de importar `PREGUNTAS_REQUERIDAS_ONBOARDING` acá
adentro a propósito: `api/tests/test_onboarding_router.py` (PR3, ya
mergeado) monkeypatchea `onboarding.PREGUNTAS_REQUERIDAS_ONBOARDING`
directo en el namespace del router — si esta función importara el
catálogo por su cuenta, ese monkeypatch dejaría de tener efecto sobre
la lógica compartida. Cada router sigue con su propio import del
catálogo (monkeypatcheable en su propio namespace) y se lo pasa
explícito a esta función pura.
"""

from dataclasses import dataclass
from typing import Mapping

from fastapi import HTTPException, status

from parser.diagnostico.guia_diagnostico import PreguntaGuia
from parser.persistencia.puerto_repositorio import PuertoRepositorioClinicas


@dataclass(frozen=True)
class EstadoOnboarding:
    completo: bool
    migracion_completada: bool
    preguntas_faltantes: list[str]


def calcular_estado_onboarding(
    migracion_completada: bool,
    respuestas: dict[str, str],
    preguntas_requeridas: Mapping[str, PreguntaGuia],
) -> EstadoOnboarding:
    preguntas_faltantes = [id_pregunta for id_pregunta in preguntas_requeridas if id_pregunta not in respuestas]
    return EstadoOnboarding(
        completo=migracion_completada and not preguntas_faltantes,
        migracion_completada=migracion_completada,
        preguntas_faltantes=preguntas_faltantes,
    )


def exigir_onboarding_completo(
    clinica_id: str,
    repo: PuertoRepositorioClinicas,
    preguntas_requeridas: Mapping[str, PreguntaGuia],
) -> None:
    """409 si el onboarding no está completo — gate que usan
    `GET /diagnostico` y `POST|GET /informe` antes de correr
    `procesar_migracion`/`interpretar_clinica`. Repite las dos lecturas
    de `repo` que ya hace `calcular_estado_onboarding` (no recibe el
    estado ya armado) para quedar autocontenida: al llamador le alcanza
    con `exigir_onboarding_completo(clinica_id, repo, preguntas)`, sin
    tener que orquestar las lecturas él mismo — una lectura extra contra
    el repositorio no pesa frente a lo que sigue si el gate pasa
    (`procesar_migracion` o encima `interpretar_clinica`)."""
    migracion_completada = repo.esta_migracion_completada(clinica_id)
    respuestas = repo.cargar_respuestas_diagnostico(clinica_id)
    estado = calcular_estado_onboarding(migracion_completada, respuestas, preguntas_requeridas)
    if not estado.completo:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El onboarding todavía no está completo: falta procesar un archivo y/o responder "
            "preguntas requeridas de la Guía de Diagnóstico.",
        )
