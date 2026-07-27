"""
pipeline.py

Punto de entrada único del parser. Lo llama el endpoint de FastAPI del
Paso 3 del onboarding (o cualquier carga posterior de datos):

    resultado = procesar_migracion(archivos, variables_previas=...)

Flujo:
  1. Por cada archivo, elige el extractor según extensión.
  2. Resuelve conflictos entre todos los archivos y variables_previas (lo
     que ya estaba en la base de la clínica — de una migración anterior,
     del wizard, o de facturas ya cargadas): si dos fuentes dan valores
     distintos con confianza empatada, la variable queda pendiente de que
     el dueño decida (ver conflictos.py), no se elige por orden de llegada.
  3. Corre el chequeo de cobertura y arma la respuesta para el frontend:
     KPIs ya calculados + preguntas pendientes ordenadas por impacto +
     conflictos pendientes de confirmación.
"""

from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from schema import KPI_BY_ID
from coverage import VariableValue, evaluar_cobertura, variables_para_wizard
from conflictos import resolver_conflictos
from extractors import excel_parser, vision_parser


EXTRACTOR_POR_EXTENSION = {
    ".xlsx": excel_parser.parsear_excel,
    ".xls": excel_parser.parsear_excel,
    ".csv": excel_parser.parsear_excel,
    ".png": vision_parser.parsear_imagen,
    ".jpg": vision_parser.parsear_imagen,
    ".jpeg": vision_parser.parsear_imagen,
    ".webp": vision_parser.parsear_imagen,
    ".pdf": vision_parser.parsear_pdf,
}


def extraer_archivo(path: str, client=None) -> dict[str, VariableValue]:
    ext = Path(path).suffix.lower()
    extractor = EXTRACTOR_POR_EXTENSION.get(ext)
    if extractor is None:
        raise ValueError(f"Formato no soportado: {ext}. Soportados: {list(EXTRACTOR_POR_EXTENSION)}")
    variables = extractor(path, client)
    nombre_archivo = Path(path).name
    return {var: replace(valor, archivo_origen=nombre_archivo) for var, valor in variables.items()}


def procesar_migracion(
    archivos: list[str],
    variables_previas: Optional[dict[str, VariableValue]] = None,
    client=None,
) -> dict:
    """
    Devuelve el payload listo para el frontend:
      {
        "kpis_calculados": {id: {...}},
        "kpis_parciales": {id: [variables_que_faltan]},
        "kpis_bloqueados_por_diseno": [ids],   # se calculan solos, no se muestran como "pendiente"
        "kpis_esperando_facturas": [ids],
        "kpis_esperando_resolucion_conflicto": {id: [variables_en_conflicto]},
        "preguntas_wizard": [ {variable, tipo, kpis_que_desbloquea, prioridad} ],
        "conflictos_pendientes": [ {variable, pregunta, opciones, permite_valor_manual} ],
        "variables_a_confirmar": [ ... ],       # baja confianza, mostrar como sugerencia
        "variables": {...}                      # snapshot completo para guardar en la DB
      }
    """
    extraidas = [extraer_archivo(a, client) for a in archivos]
    variables, conflictos = resolver_conflictos([variables_previas or {}, *extraidas])
    variables_en_conflicto = {c.variable for c in conflictos}

    cobertura = evaluar_cobertura(variables, variables_en_conflicto)
    preguntas = variables_para_wizard(cobertura)

    return {
        "kpis_calculados": {
            kpi_id: {**info, "kpi_nombre": KPI_BY_ID[kpi_id].nombre}
            for kpi_id, info in cobertura.kpis_calculados.items()
        },
        "kpis_parciales": cobertura.kpis_parciales,
        "kpis_bloqueados_por_diseno": cobertura.kpis_bloqueados_por_diseno,
        "kpis_esperando_facturas": cobertura.kpis_esperando_facturas,
        "kpis_esperando_resolucion_conflicto": cobertura.kpis_esperando_resolucion_conflicto,
        "preguntas_wizard": preguntas,
        "conflictos_pendientes": [
            {
                "variable": c.variable,
                "pregunta": f"Encontramos valores distintos para {c.variable}. ¿Cuál es correcto?",
                "opciones": c.candidatos,
                "permite_valor_manual": True,
            }
            for c in conflictos
        ],
        "variables_a_confirmar": [
            {"variable": v, "valor_sugerido": variables[v].valor, "fuente": variables[v].fuente}
            for v in cobertura.variables_baja_confianza
        ],
        "variables": variables,
    }


def resolver_conflicto(
    variable: str,
    variables_previas: dict[str, VariableValue],
    valor: Any = None,
    valor_manual: Any = None,
) -> dict:
    """
    Aplica la elección del dueño de la clínica sobre un conflicto pendiente
    (POST /onboarding/{clinica_id}/resolver-conflicto, ver README) y vuelve
    a correr procesar_migracion con esa variable ya confirmada.
    """
    valor_elegido = valor if valor_manual is None else valor_manual
    variables_actualizadas = dict(variables_previas)
    variables_actualizadas[variable] = VariableValue(
        valor=valor_elegido, fuente="confirmado_por_dueno", confianza=1.0, archivo_origen=None,
    )
    return procesar_migracion(archivos=[], variables_previas=variables_actualizadas)


def sin_archivos(variables_previas: Optional[dict[str, VariableValue]] = None) -> dict:
    """
    Caso "no subís nada" del onboarding (Paso 3 opcional): corre el mismo
    chequeo de cobertura solo contra lo que ya hubiera (normalmente nada),
    así el wizard termina preguntando el set completo — sin código aparte.
    """
    return procesar_migracion(archivos=[], variables_previas=variables_previas)
