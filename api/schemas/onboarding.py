"""
schemas/onboarding.py

Pydantic wrappers para el router `api/routers/onboarding.py`.

`ResolverConflictoRequest` espeja los parámetros de
`parser.pipeline.resolver_conflicto` que el dueño de la clínica elige en
la request — `variables_previas` NO está acá porque el router la carga
del repositorio (`repo.cargar_variables(clinica_id)`), nunca del body:
el cliente no puede mandar el estado previo de la clínica, sólo su
elección sobre el conflicto puntual.

`GuiaResponse`/`PreguntaGuiaResponse` mezclan
`PREGUNTAS_REQUERIDAS_ONBOARDING` (el catálogo fijo) con
`cargar_respuestas_diagnostico` (lo que el dueño ya contestó) para que
el cliente vea, en una sola llamada, qué preguntas obligatorias faltan
todavía — sin esto tendría que pedir el catálogo y las respuestas por
separado y cruzarlas él mismo.

`EstadoResponse` no es sólo un booleano: expone `migracion_completada` y
`preguntas_faltantes` por separado porque son las dos condiciones
independientes que `completo` combina (ver design: "explicit marker, not
inferred from variables") — un cliente que necesite guiar al dueño a
terminar el onboarding necesita saber CUÁL de las dos condiciones falta,
no sólo que falta alguna.

`MigracionResponse`/la respuesta de `resolver-conflicto` NO tienen un
schema Pydantic dedicado a propósito: `procesar_migracion`/
`resolver_conflicto` devuelven un dict con ~15 claves heterogéneas
(dataclasses anidados como `ReporteCalidad`/`Cruce`, listas de dicts
armados ad-hoc, `None` cuando no aplica) que ya está pensado como el
payload completo para el frontend (ver docstring de `procesar_migracion`
en `parser/pipeline.py`). Espejar esa forma campo por campo en un
`BaseModel` duplicaría esa lista de claves en dos lugares que se
desincronizan apenas `pipeline.py` cambie, sin ganar validación real (el
router no valida su propio output, sólo lo devuelve). El router declara
el tipo de retorno como `dict[str, Any]`: FastAPI igual lo serializa vía
`jsonable_encoder` (maneja los dataclasses anidados sin declarar nada
acá) sin necesidad de este wrapper.
"""

from typing import Any, Optional

from pydantic import BaseModel


class ResolverConflictoRequest(BaseModel):
    variable: str
    valor: Any = None
    valor_manual: Any = None
    respuestas_diagnostico: Optional[dict[str, str]] = None
    candidatos: Optional[list[dict[str, Any]]] = None
    periodos_de_escalares: Optional[dict[int, str]] = None


class PreguntaGuiaResponse(BaseModel):
    id: str
    texto: str
    bloque: int
    nombre_bloque: str
    nucleo: bool
    respuesta: Optional[str] = None


class GuiaResponse(BaseModel):
    preguntas: list[PreguntaGuiaResponse]


class RespuestasRequest(BaseModel):
    respuestas: dict[str, str]


class EstadoResponse(BaseModel):
    completo: bool
    migracion_completada: bool
    preguntas_faltantes: list[str]
