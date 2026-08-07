"""
schemas/diagnostico_informe.py

Pydantic wrappers para `GET /clinicas/{id}/diagnostico` y
`POST|GET /clinicas/{id}/informe`.

`DiagnosticoResponse.diagnostico` envuelve `resultado["diagnostico"]`
(`pipeline.procesar_migracion`) bajo una clave — a diferencia de
`migrar`/`resolver-conflicto` en `onboarding.py` (que no tienen ningún
wrapper, devuelven `dict[str, Any]` pelado), acá SÍ hay un wrapper con
nombre porque el valor de `procesar_migracion` es directamente una
lista (no un dict de ~15 claves heterogéneas): una clave le da al
cliente un sobre estable — lugar para agregar metadata más adelante
(ej. `generado_en`) sin romper el contrato — en vez de devolver un
array JSON pelado en la raíz de la respuesta.

Los ITEMS de esa lista siguen sin tipar campo por campo (`list[Any]`,
no un `BaseModel` por cada `diagnostico.Diagnostico`): cada
`Diagnostico` trae `Anomalia`/`Hipotesis`/`Contradiccion` anidados y un
enum `EstadoEvidencia` — espejar esa forma acá la duplicaría en un
segundo lugar que se desincroniza apenas `diagnostico.py` cambie, mismo
argumento que ya dejó documentado `schemas/onboarding.py` para
`migrar`/`resolver-conflicto`. Verificado en este PR: Pydantic v2
serializa objetos arbitrarios en un campo `Any` correctamente en
`model_dump(mode="json")` (dataclasses anidados y enums incluidos, sin
declarar nada más) — FastAPI usa exactamente ese `model_dump` en el
camino de `jsonable_encoder` para un `BaseModel`, así que el wrapper no
pierde nada de lo que ya tenía el `dict[str, Any]` pelado.

`InformeResponse.texto` es simple a propósito: `cargar_informe`/
`guardar_informe` (`puerto_repositorio.py`) sólo manejan un `str`, no
un dataclass anidado — acá sí vale la pena un campo tipado de verdad
en vez de `Any`.
"""

from typing import Any

from pydantic import BaseModel


class DiagnosticoResponse(BaseModel):
    diagnostico: list[Any]


class InformeResponse(BaseModel):
    texto: str
