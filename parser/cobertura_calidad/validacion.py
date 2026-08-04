"""
validacion.py

Guardas deterministas que corren DESPUÉS de resolver conflictos y ANTES de
que cualquier valor se use para calcular un KPI o se muestre al dueño de
la clínica. No arreglan nada — lo que no pasa la guarda queda en
cuarentena (fuera de `variables`, visible en `variables_en_cuarentena`) en
vez de propagarse en silencio, que es lo que pasaba antes de este módulo
(ver hallazgos A y B del informe de deficiencias del agente de diagnóstico).

Tres clases de chequeo, en orden:
  1. Tipo: ¿el valor extraído tiene la forma que schema.py declara para esa
     variable? (dict/list/número)
  2. Forma: ¿el valor es plausible para lo que representa? (no negativo, no
     una fracción entre 0 y 1 travestida de conteo entero — la trampa real
     que confundió no_shows con la columna de tasa)
  3. Origen: ¿una variable interna (la calcula el sistema) está llegando
     de un extractor, que nunca debería escribirla?
  4. Identidad: ¿es consistente con otras variables ya aceptadas? (un
     sub-conjunto no puede superar a su superconjunto, con tolerancia)
"""

from dataclasses import dataclass
from typing import Any, Optional

from parser.vocabulario.schema import INTERNAL_VARIABLES, VARIABLE_TYPES


@dataclass
class Rechazo:
    variable: str
    motivo: str


def validar_tipo(var: str, valor: Any) -> Optional[str]:
    tipo = VARIABLE_TYPES.get(var)
    if tipo is None:
        return None
    if tipo == "dict":
        return None if isinstance(valor, dict) else f"se esperaba dict, llegó {type(valor).__name__}"
    if tipo == "list":
        return None if isinstance(valor, list) else f"se esperaba list, llegó {type(valor).__name__}"
    if tipo == "ledger":
        # {paciente_id: [eventos]} — un dict cuyos valores son listas
        # (de eventos), no un dict plano {categoria: número} como
        # ingreso_por_paciente. Fase 2 (matching.py + metricas_paciente.py).
        if not isinstance(valor, dict):
            return f"se esperaba ledger (dict de listas), llegó {type(valor).__name__}"
        if not all(isinstance(v, list) for v in valor.values()):
            return "se esperaba un ledger {paciente_id: [eventos]} — algún valor no es una lista"
        return None
    if tipo in ("int", "float"):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return f"se esperaba número, llegó {type(valor).__name__}"
    return None


def validar_forma(var: str, valor: Any) -> Optional[str]:
    tipo = VARIABLE_TYPES.get(var)
    if tipo not in ("int", "float") or isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    if valor < 0:
        return f"valor negativo ({valor}) para una variable que no puede serlo"
    if tipo == "int" and 0 < valor < 1:
        return (
            f"valor {valor} es una fracción entre 0 y 1 para una variable de tipo "
            f"conteo — señal típica de haber leído la columna de TASA en vez de la "
            f"columna de CONTEO (ver hallazgo 1.3)"
        )
    return None


def validar_origen(var: str, fuente: str) -> Optional[str]:
    if var in INTERNAL_VARIABLES and fuente.startswith("migracion_"):
        return (
            f"'{var}' es una variable interna (la calcula el sistema, nunca viene "
            f"de un archivo migrado) pero llegó de fuente '{fuente}'"
        )
    return None


def validar_variable(var: str, valor: Any, fuente: str) -> Optional[str]:
    """Chequeos que no dependen de otras variables. None si está OK."""
    return validar_tipo(var, valor) or validar_forma(var, valor) or validar_origen(var, fuente)


# (variable_menor, variable_mayor): variable_menor no puede superar a
# variable_mayor — son sub-conjuntos del mismo embudo o la misma cuenta.
IDENTIDADES: list[tuple[str, str]] = [
    ("presupuestos_aceptados", "presupuestos_emitidos"),
    ("no_shows", "turnos_agendados"),
    # Hallazgo #4: una cancelación presupone un turno agendado.
    # `pacientes_activos_cartera` (stock) NO tiene una pareja acá a propósito
    # — ver schema.py: puede legítimamente invertirse contra el flujo
    # pacientes_atendidos_periodo, forzarlo generaría cuarentenas falsas.
    ("turnos_cancelados", "turnos_agendados"),
    ("turnos_agendados", "consultas_nuevas_mes"),
    ("monto_cobrado", "monto_facturado"),
    ("tratamientos_completados", "tratamientos_iniciados"),
    ("pacientes_reactivados", "pacientes_inactivos_contactados"),
    ("pacientes_vuelven_control", "pacientes_dados_alta"),
]

# Margen para no confundir un problema real con simple desalineación de
# períodos entre dos variables que no vienen exactamente del mismo mes.
TOLERANCIA_IDENTIDAD = 1.05


def validar_identidades(escalares: dict[str, Any]) -> list[Rechazo]:
    """`escalares`: var -> valor numérico ya resuelto (sin VariableValue)."""
    violaciones = []
    for menor, mayor in IDENTIDADES:
        if menor not in escalares or mayor not in escalares:
            continue
        v_menor, v_mayor = escalares[menor], escalares[mayor]
        if isinstance(v_menor, bool) or isinstance(v_mayor, bool):
            continue
        if not isinstance(v_menor, (int, float)) or not isinstance(v_mayor, (int, float)):
            continue
        if v_menor > v_mayor * TOLERANCIA_IDENTIDAD:
            margen = int((TOLERANCIA_IDENTIDAD - 1) * 100)
            violaciones.append(Rechazo(
                menor,
                f"{menor}={v_menor} no puede ser mayor que {mayor}={v_mayor} "
                f"(con {margen}% de tolerancia por desalineación de período)",
            ))
    return violaciones
