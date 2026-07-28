"""
formato.py

Formato de números para MOSTRAR al dueño de la clínica y para que el
agente los CITE en su texto — nunca para razonar. Las 20 fórmulas de
schema.py y el agente siempre trabajan con el número crudo; esto solo
maquilla la salida (hallazgo 1.2 del informe de deficiencias: el agente
devolvía "15000" en vez de "$15.000").
"""

from typing import Any, Optional


def fmt_numero(valor: Optional[float], decimales: int = 0) -> str:
    """15000 -> "15.000"; 1234.5 -> "1.234,5" (separador de miles ARG)."""
    if valor is None:
        return "-"
    texto = f"{valor:,.{decimales}f}"
    texto = texto.replace(",", "␟").replace(".", ",").replace("␟", ".")
    return texto


def fmt_ars(valor: Optional[float]) -> str:
    if valor is None:
        return "-"
    return f"${fmt_numero(round(valor))}"


def fmt_pct(valor: Optional[float], decimales: int = 1) -> str:
    if valor is None:
        return "-"
    return f"{fmt_numero(valor, decimales)}%"


def fmt_horas(valor: Optional[float], decimales: int = 1) -> str:
    if valor is None:
        return "-"
    return f"{fmt_numero(valor, decimales)} hs"


UNIDADES_ARS = {"$", "$/hora", "$/paciente"}
UNIDADES_HORAS = {"hs/semana", "hs/mes"}


def fmt_por_unidad(valor: Any, unidad: str) -> str:
    """Formatea un valor de KPI según su unidad declarada en KPIFormula.unidad."""
    if valor is None:
        return "-"
    if isinstance(valor, dict):
        return "; ".join(f"{k}: {fmt_por_unidad(v, unidad)}" for k, v in valor.items())
    if unidad in UNIDADES_ARS:
        return fmt_ars(valor)
    if unidad == "%":
        return fmt_pct(valor)
    if unidad in UNIDADES_HORAS:
        return fmt_horas(valor)
    if unidad == "min":
        return f"{fmt_numero(valor, 1)} min"
    if unidad == "conteo":
        return fmt_numero(valor)
    return fmt_numero(valor, 2)
