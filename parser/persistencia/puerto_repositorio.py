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
"""

from typing import Protocol

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
