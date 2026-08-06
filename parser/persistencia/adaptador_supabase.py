"""
adaptador_supabase.py

Único lugar del código que conoce Supabase. Implementa
`PuertoRepositorioClinicas` (ver puerto_repositorio.py) contra dos tablas
(`schema.sql` tiene el DDL completo, se corre a mano una vez en el SQL
Editor de Supabase — el cliente REST no puede crear tablas):

  variables               — columnas simples de VariableValue (valor,
                             periodo, fuente, confianza, archivo_origen,
                             metodo) + `detalle` JSONB con todo lo
                             anidado/opcional (serie, etiquetas_originales,
                             periodos_no_reconocidos, etiqueta_fila,
                             trazabilidad). `unique(clinica_id, variable)`
                             — una fila vigente por variable por clínica,
                             UPSERT la pisa.
  respuestas_diagnostico   — dict simple {pregunta_id: respuesta}.

Por qué `detalle` es JSONB y no columnas: `VariableValue`/`Trazabilidad`
ganaron campos varias veces en la vida de este proyecto (Fase 0, Fase 1,
Bug #1a...) — todo relacional hubiera significado una migración de schema
cada vez. Ver la comparación completa en la conversación de diseño
2026-08-06 (memoria del proyecto).

Autenticación: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY por variables de
entorno (falla cerrado si faltan, mismo criterio que puerto_geometria.py).
Se usa la service_role key — bypassea RLS por completo — porque hoy no
hay ningún login real: el backend decide a qué `clinica_id` accede, no un
usuario logueado. Migrar a la `anon` key + políticas de RLS por clínica
el día que exista Auth de verdad (anotado, no se resuelve acá).
"""

import os
from dataclasses import asdict
from typing import Any, Optional

from parser.cobertura_calidad.coverage import VariableValue
from parser.cobertura_calidad.trazabilidad import Trazabilidad

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None


def _fila_desde_variable(clinica_id: str, variable: str, vv: VariableValue) -> dict[str, Any]:
    """Traduce un VariableValue a la forma de fila de `variables`. Todo lo
    anidado/opcional que no tiene columna propia va a `detalle` (None si
    no hay nada que guardar, para no ensuciar la fila con claves vacías)."""
    detalle: dict[str, Any] = {}
    if vv.serie is not None:
        detalle["serie"] = vv.serie
    if vv.etiquetas_originales is not None:
        detalle["etiquetas_originales"] = vv.etiquetas_originales
    if vv.periodos_no_reconocidos is not None:
        detalle["periodos_no_reconocidos"] = vv.periodos_no_reconocidos
    if vv.etiqueta_fila is not None:
        detalle["etiqueta_fila"] = vv.etiqueta_fila
    if vv.trazabilidad is not None:
        detalle["trazabilidad"] = asdict(vv.trazabilidad)

    return {
        "clinica_id": clinica_id,
        "variable": variable,
        "valor": vv.valor,
        "periodo": vv.periodo,
        "fuente": vv.fuente,
        "confianza": vv.confianza,
        "archivo_origen": vv.archivo_origen,
        "metodo": vv.metodo,
        "detalle": detalle or None,
    }


def _variable_desde_fila(fila: dict[str, Any]) -> VariableValue:
    """Inverso de `_fila_desde_variable`: reconstruye el VariableValue
    completo, desempaquetando `detalle`."""
    detalle = fila.get("detalle") or {}
    trazabilidad_dict = detalle.get("trazabilidad")
    return VariableValue(
        valor=fila["valor"],
        fuente=fila["fuente"],
        confianza=fila["confianza"],
        archivo_origen=fila.get("archivo_origen"),
        serie=detalle.get("serie"),
        periodo=fila.get("periodo"),
        etiquetas_originales=detalle.get("etiquetas_originales"),
        periodos_no_reconocidos=detalle.get("periodos_no_reconocidos"),
        trazabilidad=Trazabilidad(**trazabilidad_dict) if trazabilidad_dict else None,
        metodo=fila.get("metodo"),
        etiqueta_fila=detalle.get("etiqueta_fila"),
    )


class AdaptadorSupabase:
    """Adapter real (driven) de `PuertoRepositorioClinicas` contra
    Supabase. `cliente` es inyectable para tests (cualquier objeto con
    `.table(nombre).select/eq/upsert/execute` alcanza, no hace falta el
    SDK real — ver test_adaptador_supabase.py)."""

    def __init__(
        self,
        cliente: Optional[Any] = None,
        url: Optional[str] = None,
        key: Optional[str] = None,
    ):
        if cliente is not None:
            self._cliente = cliente
            return

        url = url or os.environ.get("SUPABASE_URL")
        key = key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError(
                "Faltan SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY en el entorno: sin "
                "credenciales no se conecta a ninguna base real (falla cerrado)."
            )
        assert create_client is not None, "Instalar el SDK: pip install supabase"
        self._cliente = create_client(url, key)

    def cargar_variables(self, clinica_id: str) -> dict[str, VariableValue]:
        respuesta = self._cliente.table("variables").select("*").eq("clinica_id", clinica_id).execute()
        return {fila["variable"]: _variable_desde_fila(fila) for fila in respuesta.data}

    def guardar_variables(self, clinica_id: str, variables: dict[str, VariableValue]) -> None:
        if not variables:
            return
        filas = [_fila_desde_variable(clinica_id, var, vv) for var, vv in variables.items()]
        self._cliente.table("variables").upsert(filas, on_conflict="clinica_id,variable").execute()

    def cargar_respuestas_diagnostico(self, clinica_id: str) -> dict[str, str]:
        respuesta = (
            self._cliente.table("respuestas_diagnostico").select("*").eq("clinica_id", clinica_id).execute()
        )
        return {fila["pregunta_id"]: fila["respuesta"] for fila in respuesta.data}

    def guardar_respuestas_diagnostico(self, clinica_id: str, respuestas: dict[str, str]) -> None:
        if not respuestas:
            return
        filas = [
            {"clinica_id": clinica_id, "pregunta_id": pregunta_id, "respuesta": respuesta}
            for pregunta_id, respuesta in respuestas.items()
        ]
        self._cliente.table("respuestas_diagnostico").upsert(filas, on_conflict="clinica_id,pregunta_id").execute()
