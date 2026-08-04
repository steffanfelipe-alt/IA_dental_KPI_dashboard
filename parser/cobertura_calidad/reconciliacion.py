"""
reconciliacion.py

Fase 3 del plan de confiabilidad del agente de diagnóstico (hallazgo E):
la mayoría de las planillas reales ya traen, al lado de los conteos
crudos, la tasa/porcentaje ya calculado (ej. "Tasa no-show", "Tasa de
cobro") — es redundancia gratis que el sistema no estaba usando. Este
módulo recalcula cada tasa con las variables que se aceptaron y la
compara contra la que la propia planilla declara (extraída en
excel_parser.extraer_tasas_declaradas). Si no coinciden, alguna variable
está mal — típicamente el extractor tomó la columna de tasa en vez de la
de conteo, o viceversa.

Caso real verificado con el fixture de evals: no_shows terminó con un
valor (57) que pasa todas las guardas de validacion.py (es un entero
positivo, no supera a turnos_agendados) pero implica una tasa de 78%
cuando la propia hoja declara 22% — solo la reconciliación contra ese
dato redundante lo detecta.

No intenta adivinar CUÁL variable de un KPI con más de una está mal: si
esa variable también participa de otro KPI que SÍ cierra contra su tasa
declarada, se la deja (está corroborada); si no, se pone en cuarentena
junto con el resto de variables que solo sirven para el KPI que no cierra.
"""

from dataclasses import dataclass
from typing import Any

from parser.vocabulario.schema import KPI_BY_ID

TOLERANCIA_PCT = 5.0  # puntos porcentuales de margen antes de marcar discrepancia

# Marca de fuente que pone derivacion.py. Definida acá (no importada de
# derivacion.py) para no crear un import circular: derivacion.py necesita
# saber de reconciliación, pero no al revés.
FUENTE_DERIVADA = "derivado_de_tasa"


def _es_derivada(vv: Any) -> bool:
    return getattr(vv, "fuente", "") == FUENTE_DERIVADA


@dataclass
class Discrepancia:
    kpi_id: int
    kpi_nombre: str
    calculado: float
    declarado: float
    variables: list[str]


def reconciliar(
    variables: dict[str, Any],
    tasas_declaradas: dict[int, Any],
) -> tuple[set[str], list[Discrepancia]]:
    """
    `variables`: var -> VariableValue ya filtradas por validacion.py.
    `tasas_declaradas`: kpi_id -> TasaDeclarada (ver
    excel_parser.extraer_tasas_declaradas); se usa `.vigente`, el % que la
    planilla declara para el período actual.

    Devuelve (variables_a_poner_en_cuarentena, discrepancias) — nunca
    modifica `variables` directamente, así el llamador decide qué hacer.

    Un KPI que involucre una variable DERIVADA de su propia tasa se saltea:
    esa variable satisface la identidad por construcción, así que el KPI
    cerraría siempre y daría por corroborada a la otra variable de la
    fórmula sin haberla verificado nunca (ver derivacion.py).
    """
    if not tasas_declaradas:
        return set(), []

    kpis_ok: set[int] = set()
    kpis_mal: dict[int, Discrepancia] = {}

    for kpi_id, tasa in tasas_declaradas.items():
        kpi = KPI_BY_ID.get(kpi_id)
        if kpi is None or kpi.unidad != "%":
            continue
        requeridas = kpi.variables
        if not all(v in variables for v in requeridas):
            continue
        if any(_es_derivada(variables[v]) for v in requeridas):
            continue  # circularidad: ver docstring
        declarado = tasa.vigente
        payload = {v: variables[v].valor for v in requeridas}
        try:
            calculado = kpi.calcular(payload)
        except Exception:
            continue
        if calculado is None or not isinstance(calculado, (int, float)):
            continue

        if abs(calculado - declarado) <= TOLERANCIA_PCT:
            kpis_ok.add(kpi_id)
        else:
            kpis_mal[kpi_id] = Discrepancia(kpi_id, kpi.nombre, calculado, declarado, list(requeridas))

    if not kpis_mal:
        return set(), []

    # Una variable que también alimenta un KPI que SÍ cerró queda
    # corroborada por ese otro lado — no se pone en cuarentena solo porque
    # comparte fórmula con un KPI que no cerró.
    vars_corroboradas = {v for kid in kpis_ok for v in KPI_BY_ID[kid].variables}

    a_cuarentena: set[str] = set()
    for d in kpis_mal.values():
        for v in d.variables:
            if v not in vars_corroboradas:
                a_cuarentena.add(v)

    return a_cuarentena, list(kpis_mal.values())
