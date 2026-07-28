"""
derivacion.py

Completa una variable que la planilla NO trae como columna cruda pero que
sí se puede despejar de una tasa que la planilla ya trae calculada.

Caso motivador (real): una hoja mensual trae "Tasa no-show" pero ninguna
columna con el conteo de ausencias. Hasta ahora `no_shows` quedaba
pendiente en el wizard aunque el dato estuviera ahí, implícito:
`no_shows = turnos_agendados × tasa / 100`.

Por qué esto no repite el error original
----------------------------------------
El bug que originó todo el plan de confiabilidad fue *adivinar* qué
representaba una columna. Acá no se adivina nada: `schema.KPIFormula`
declara explícitamente, escrito a mano, cuál variable es el numerador y
cuál el denominador de cada KPI porcentual. Un KPI que no los declara
(ej. el 10, cuyo numerador es una suma de dos variables, o el 16, que usa
variables internas) simplemente nunca dispara derivación. El default es
no hacer nada.

Reglas de seguridad, todas deliberadas:

1. **Solo se despeja el numerador.** `num = den × tasa/100` propaga el
   error de la tasa de forma lineal; `den = num × 100/tasa` lo amplifica
   como 1/tasa y se dispara con tasas chicas. Solo la dirección estable.
2. **Solo si la variable está ausente de verdad.** Nunca pisa un valor
   extraído, y el llamador tampoco le pasa las que están en cuarentena:
   si una variable fue rechazada por una causa, derivarla sería blanquearla.
3. **Se marca como derivada** (`fuente=FUENTE_DERIVADA`, confianza
   `CONFIANZA_DERIVADA`) para que caiga sola en `variables_a_confirmar` y
   se muestre como sugerencia, nunca como dato observado.
4. **Se valida** con `validacion.validar_variable` antes de aceptarse,
   igual que cualquier valor extraído.
5. **Se registra de qué KPI salió**, para que `reconciliacion.py` pueda
   excluir ese KPI y no darse por corroborado contra un dato que satisface
   la identidad por construcción (ver `_es_derivada` allá).
"""

from dataclasses import dataclass
from typing import Optional

from coverage import VariableValue
from reconciliacion import FUENTE_DERIVADA
from schema import KPI_BY_ID, VARIABLE_TYPES
from validacion import validar_variable

CONFIANZA_DERIVADA = 0.6  # < 0.7: cae en "a confirmar", nunca se presenta como dato duro


@dataclass
class Derivacion:
    variable: str
    kpi_id: int
    valor: float
    desde_denominador: str
    tasa_declarada: float


def _despejar(denominador: float, tasa_pct: float, variable: str) -> Optional[float]:
    """numerador = denominador × tasa%. Redondea a entero si la variable es de conteo."""
    if not isinstance(denominador, (int, float)) or isinstance(denominador, bool):
        return None
    if not isinstance(tasa_pct, (int, float)) or isinstance(tasa_pct, bool):
        return None
    valor = denominador * tasa_pct / 100
    if VARIABLE_TYPES.get(variable) == "int":
        return float(round(valor))
    return round(valor, 2)


def derivar_variables_faltantes(
    variables: dict[str, VariableValue],
    tasas_declaradas: dict[int, object],
) -> tuple[dict[str, VariableValue], list[Derivacion]]:
    """
    `variables`: las que sobrevivieron a validación + reconciliación.
    `tasas_declaradas`: kpi_id -> TasaDeclarada (ver excel_parser).

    Devuelve (variables_nuevas, derivaciones). No modifica `variables`:
    el llamador decide cómo integrarlas.
    """
    nuevas: dict[str, VariableValue] = {}
    derivaciones: list[Derivacion] = []

    for kpi_id, tasa in tasas_declaradas.items():
        kpi = KPI_BY_ID.get(kpi_id)
        if kpi is None or not kpi.numerador or not kpi.denominador:
            continue  # KPI sin estructura declarada: nunca se deriva
        num, den = kpi.numerador, kpi.denominador

        # Regla 2: solo se completa un hueco real.
        if num in variables or num in nuevas or den not in variables:
            continue

        vv_den = variables[den]
        valor = _despejar(vv_den.valor, getattr(tasa, "vigente", None), num)
        if valor is None:
            continue

        # Regla 4: pasa por las mismas guardas que cualquier valor extraído.
        if validar_variable(num, valor, FUENTE_DERIVADA):
            continue

        serie = _derivar_serie(vv_den.serie, getattr(tasa, "serie", None), num)

        nuevas[num] = VariableValue(
            valor=valor,
            fuente=FUENTE_DERIVADA,
            confianza=CONFIANZA_DERIVADA,
            archivo_origen=vv_den.archivo_origen,
            serie=serie,
            periodo=(list(serie.keys())[-1] if serie else vv_den.periodo),
        )
        derivaciones.append(Derivacion(
            variable=num, kpi_id=kpi_id, valor=valor,
            desde_denominador=den, tasa_declarada=tasa.vigente,
        ))

    return nuevas, derivaciones


def _derivar_serie(
    serie_den: Optional[dict], serie_tasa: Optional[dict], variable: str,
) -> Optional[dict]:
    """
    Serie del numerador período por período, sobre los períodos que
    denominador y tasa tienen en común — así el KPI derivado conserva su
    eje temporal y el agente puede razonar sobre tendencia (Fase 2), en vez
    de quedarse con un escalar suelto.
    """
    if not serie_den or not serie_tasa:
        return None
    resultado = {}
    for periodo, valor_den in serie_den.items():
        if periodo not in serie_tasa:
            continue
        valor = _despejar(valor_den, serie_tasa[periodo], variable)
        if valor is not None:
            resultado[periodo] = valor
    return resultado or None
