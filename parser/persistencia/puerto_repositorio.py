"""
puerto_repositorio.py

Puerto driven (Protocol/Adapter, mismo espíritu que puerto_llm.py y
puerto_geometria.py) para la persistencia de una clínica: guardar y
recargar el `dict[str, VariableValue]` que circula por
`pipeline.procesar_migracion` (parámetro `variables_previas` / valor de
retorno), y las respuestas de la Guía de Diagnóstico
(`respuestas_diagnostico`).

Los callers de este puerto (el futuro endpoint de FastAPI, y cualquier
otro entry point que necesite recargar el estado de una clínica) no
conocen Supabase ni ningún SDK de base de datos — sólo hablan contra
`PuertoRepositorioClinicas`. El adapter real (`AdaptadorSupabase`, en
`adaptador_supabase.py`) es el único lugar que sabe que la base es
Supabase/Postgres.

Separado en dos pares de métodos (variables / respuestas_diagnostico) en
vez de uno solo genérico porque `procesar_migracion` ya los recibe como
parámetros separados — alimentan cosas distintas (las 21 fórmulas de
`schema.py` vs. el contexto cualitativo de `diagnostico.py`), y mezclarlos
en un único "guardar clínica" escondería esa distinción que el resto del
sistema ya respeta.

Los seis métodos agregados en el cambio api-auth-onboarding-diagnostico
(2026-08-06) cubren lo que el futuro `api/` necesita para el ciclo
clínica → migración → informe:

  crear_clinica / obtener_owner_id       — alta de clínica y el guard de
                                            ownership de las rutas HTTP
                                            (un usuario autenticado solo
                                            puede leer/escribir su propia
                                            clínica).
  marcar_migracion_completada /
  esta_migracion_completada              — la señal explícita de "el
                                            archivo ya se procesó" que
                                            consume GET /estado; no se
                                            infiere de `variables` no
                                            vacío (ver design del cambio).
  cargar_informe / guardar_informe       — el informe narrativo de Opus,
                                            generate-once: POST /informe
                                            llama al LLM solo si
                                            `cargar_informe` devuelve None.

Los dos métodos agregados 2026-08-07 (idempotencia de POST /clinicas):

  obtener_respuesta_idempotente /
  guardar_respuesta_idempotente          — si el cliente manda un header
                                            Idempotency-Key, el router
                                            chequea si esa clave ya tiene
                                            una respuesta guardada antes
                                            de crear la clínica; si la
                                            tiene, la devuelve tal cual
                                            en vez de insertar de nuevo.
"""

from typing import Any, Protocol

from parser.cobertura_calidad.coverage import VariableValue


class PuertoRepositorioClinicas(Protocol):
    """Lo único que la persistencia de una clínica necesita: cargar y
    guardar sus variables, y cargar y guardar sus respuestas de la Guía
    de Diagnóstico."""

    def cargar_variables(self, clinica_id: str) -> dict[str, VariableValue]:
        ...

    def guardar_variables(self, clinica_id: str, variables: dict[str, VariableValue]) -> None:
        ...

    def cargar_respuestas_diagnostico(self, clinica_id: str) -> dict[str, str]:
        ...

    def guardar_respuestas_diagnostico(self, clinica_id: str, respuestas: dict[str, str]) -> None:
        ...

    def crear_clinica(self, nombre: str, owner_id: str) -> str:
        ...

    def obtener_owner_id(self, clinica_id: str) -> str | None:
        ...

    def marcar_migracion_completada(self, clinica_id: str) -> None:
        ...

    def esta_migracion_completada(self, clinica_id: str) -> bool:
        ...

    def cargar_informe(self, clinica_id: str) -> str | None:
        ...

    def guardar_informe(self, clinica_id: str, texto: str) -> None:
        ...

    def obtener_respuesta_idempotente(self, clave: str, owner_id: str) -> dict[str, Any] | None:
        ...

    def guardar_respuesta_idempotente(self, clave: str, owner_id: str, respuesta: dict[str, Any]) -> None:
        ...
