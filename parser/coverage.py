"""
coverage.py

Dado un set de variables ya normalizadas (por migración y/o wizard),
determina:
  - qué KPIs se pueden calcular ya mismo (con qué valor y confianza)
  - qué KPIs quedan parciales, y cuál es la ÚNICA variable que falta
  - la lista deduplicada de variables pendientes para mandar al wizard
    (una variable compartida por 3 KPIs aparece una sola vez)

Este es el reemplazo del chequeo "por KPI completo" que se había diagramado
al principio: acá se chequea variable por variable, así el wizard nunca
repite una pregunta que ya se puede inferir de otra parte del embudo.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from schema import KPI_FORMULAS, INTERNAL_VARIABLES, SOLO_MIGRACION_O_SISTEMA, VARIABLE_TYPES
from preguntas_wizard import obtener_pregunta


@dataclass
class VariableValue:
    valor: Any
    fuente: str            # "migracion_excel" | "migracion_foto" | "wizard" | "sistema" | "confirmado_por_dueno"
    confianza: float = 1.0  # 0-1. Baja confianza => se muestra como sugerencia a confirmar, no se da por hecho.
    archivo_origen: Optional[str] = None  # nombre de archivo, o "wizard"/"sistema" si no viene de un archivo


@dataclass
class Conflicto:
    variable: str
    candidatos: list[dict] = field(default_factory=list)  # [{"valor", "archivo", "fuente", "confianza"}]


@dataclass
class CoverageResult:
    kpis_calculados: dict[int, dict] = field(default_factory=dict)
    kpis_parciales: dict[int, list[str]] = field(default_factory=dict)   # id -> variables que faltan
    kpis_bloqueados_por_diseno: list[int] = field(default_factory=list)  # variables internas, no se piden nunca
    kpis_esperando_facturas: list[int] = field(default_factory=list)     # variables financieras, solo migración
    kpis_esperando_resolucion_conflicto: dict[int, list[str]] = field(default_factory=dict)  # id -> variables en conflicto
    variables_pendientes: list[str] = field(default_factory=list)        # deduplicadas, listas para el wizard
    variables_baja_confianza: list[str] = field(default_factory=list)    # para confirmar, no repreguntar desde cero


def evaluar_cobertura(
    variables: dict[str, VariableValue],
    variables_en_conflicto: Optional[set[str]] = None,
) -> CoverageResult:
    resultado = CoverageResult()
    pendientes_set: set[str] = set()
    variables_en_conflicto = variables_en_conflicto or set()

    for kpi in KPI_FORMULAS:
        requeridas = kpi.variables
        faltantes = [v for v in requeridas if v not in variables]
        internas_faltantes = [v for v in faltantes if v in INTERNAL_VARIABLES]
        conflicto_faltantes = [v for v in faltantes if v in variables_en_conflicto]
        financieras_faltantes = [v for v in faltantes if v in SOLO_MIGRACION_O_SISTEMA]

        if internas_faltantes:
            # Estas nunca se preguntan al dueño de la clínica: las calcula
            # el propio sistema (comparación histórica, conteo interno).
            resultado.kpis_bloqueados_por_diseno.append(kpi.id)
            continue

        if conflicto_faltantes:
            # Hay valores distintos sin resolver para alguna variable que
            # este KPI necesita: no se calcula ni se pregunta como si fuera
            # nueva — se muestra como conflicto a resolver (ver conflictos.py).
            resultado.kpis_esperando_resolucion_conflicto[kpi.id] = conflicto_faltantes
            continue

        if financieras_faltantes:
            # Estas tampoco se preguntan — dependen de facturas migradas o
            # de la integración con el sistema de cobros/agenda. El KPI
            # queda visible como "esperando facturas", no como pregunta.
            resultado.kpis_esperando_facturas.append(kpi.id)
            continue

        if faltantes:
            resultado.kpis_parciales[kpi.id] = faltantes
            pendientes_set.update(faltantes)
            continue

        payload = {k: variables[k].valor for k in requeridas}
        valor = kpi.calcular(payload)
        confianza_min = min(variables[k].confianza for k in requeridas)

        resultado.kpis_calculados[kpi.id] = {
            "nombre": kpi.nombre,
            "valor": valor,
            "unidad": kpi.unidad,
            "confianza": confianza_min,
            "fuentes": sorted({variables[k].fuente for k in requeridas}),
        }
        if confianza_min < 0.7:
            resultado.variables_baja_confianza.extend(
                k for k in requeridas if variables[k].confianza < 0.7
            )

    resultado.variables_pendientes = sorted(pendientes_set)
    resultado.variables_baja_confianza = sorted(set(resultado.variables_baja_confianza))
    return resultado


def variables_para_wizard(resultado: CoverageResult) -> list[dict]:
    """
    Arma la lista de preguntas que el wizard debe mostrar, con contexto de
    qué KPIs desbloquea cada una — esto es lo que le permite al wizard
    priorizar (ej. mostrar primero las variables que desbloquean más KPIs).
    """
    impacto: dict[str, list[int]] = {}
    for kpi_id, faltantes in resultado.kpis_parciales.items():
        for var in faltantes:
            impacto.setdefault(var, []).append(kpi_id)

    preguntas = []
    for var, kpis in impacto.items():
        pregunta = obtener_pregunta(var)
        preguntas.append({
            "variable": var,
            "tipo": VARIABLE_TYPES.get(var, "text"),
            "pregunta": pregunta.pregunta if pregunta else f"(falta definir pregunta para {var})",
            "referencia_guia": pregunta.referencia_guia if pregunta else None,
            "adaptada_de_la_guia": pregunta.adaptada if pregunta else None,
            "kpis_que_desbloquea": sorted(kpis),
            "prioridad": len(kpis),  # más KPIs desbloqueados = se pregunta antes
        })
    return sorted(preguntas, key=lambda p: -p["prioridad"])
