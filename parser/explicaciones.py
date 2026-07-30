"""
explicaciones.py

Traduce a lenguaje de dueño de clínica los motivos técnicos que ya
producen validacion.py, reconciliacion.py y derivacion.py. No toca
ninguno de esos tres módulos — los motivos que arman siguen siendo los
mismos strings de siempre (los tests que dependen de ellos no cambian),
esto sólo los RECONOCE (son un catálogo finito, ver validacion.py) y les
da una segunda voz.

Fase I2: nace de una sesión real de Felipe probando el sistema — vio
"se esperaba ledger (dict de listas), llegó int" y no supo qué hacer con
eso. El principio: nunca mentir sobre el motivo técnico (sigue
disponible, `motivo_tecnico`), pero no obligar a nadie a leerlo primero.

Si un motivo no matchea ningún patrón conocido (validacion.py agregó uno
nuevo y esto no se actualizó), se devuelve el motivo técnico tal cual —
nunca se rompe por un mensaje que no reconoce.
"""

import re
from typing import Any, Optional

from schema import METRICAS


def nombre_humano(var: str) -> str:
    """schema.METRICAS[var].nombre_humano si existe, o la variable cruda
    como fallback — mismo patrón que cruces._nombre_humano()."""
    info = METRICAS.get(var)
    return info.nombre_humano if info else var


def _fmt(valor: Any) -> str:
    if isinstance(valor, float):
        return f"{valor:,.2f}".rstrip("0").rstrip(".")
    return str(valor)


# ---------------------------------------------------------------------------
# Cuarentena — validacion.py (validar_tipo/validar_forma/validar_origen) y
# validar_identidades. Un patrón por cada motivo que esos generan.
# ---------------------------------------------------------------------------

def explicar_cuarentena(var: str, info: dict) -> str:
    """`info`: el dict que arma pipeline.py en variables_en_cuarentena —
    trae "motivo" siempre, y opcionalmente "discrepancia" o
    "reemplazada_por_derivacion"."""
    nombre = nombre_humano(var)

    if info.get("reemplazada_por_derivacion"):
        return (
            f"\"{nombre}\" se había rechazado, pero el sistema encontró la manera "
            f"de calcularlo de otra forma — ya está resuelto, esta fila queda sólo "
            f"como historial."
        )

    motivo = info.get("motivo", "")

    if info.get("discrepancia") is not None:
        d = info["discrepancia"]
        return (
            f"La planilla dice {_fmt(d['declarado'])}% para \"{d['kpi_nombre']}\", pero "
            f"con el valor de \"{nombre}\" que se extrajo, el sistema calcula "
            f"{_fmt(d['calculado'])}%. Uno de los dos números está mal, o los dos "
            f"hablan de meses distintos — revisá la planilla."
        )

    m = re.match(r"se esperaba dict, llegó (\w+)", motivo)
    if m:
        return (
            f"\"{nombre}\" tiene que venir desglosado por categoría, y llegó un solo "
            f"número ({m.group(1)}). Revisá si la hoja de origen tiene una columna "
            f"para agrupar (ej. tipo de tratamiento, tarea)."
        )

    m = re.match(r"se esperaba list, llegó (\w+)", motivo)
    if m:
        return (
            f"\"{nombre}\" tiene que ser una lista de elementos, y llegó un dato "
            f"suelto ({m.group(1)}). Esta variable normalmente se completa a mano, "
            f"no se extrae de un archivo."
        )

    if motivo.startswith("se esperaba ledger"):
        return (
            f"El sistema esperaba un historial por paciente (una fila por cada cosa "
            f"que le pasó a un paciente) y encontró un número suelto. Ese dato no se "
            f"está usando — si querés el historial completo, hace falta un archivo "
            f"con identificador de paciente y fecha por fila (ej. un export de "
            f"cobros o de turnos)."
        )

    if "algún valor no es una lista" in motivo:
        return (
            f"El historial por paciente que se armó salió con un problema interno — "
            f"algún paciente quedó con un dato suelto en vez de su lista de eventos. "
            f"No es un problema del archivo, es del sistema."
        )

    m = re.match(r"se esperaba número, llegó (\w+)", motivo)
    if m:
        return (
            f"\"{nombre}\" tiene que ser un número, y se extrajo algo que no lo es "
            f"({m.group(1)}). Probablemente se tomó la columna equivocada."
        )

    m = re.match(r"valor negativo \(([^)]+)\) para una variable que no puede serlo", motivo)
    if m:
        return f"\"{nombre}\" dio un valor negativo ({m.group(1)}), y esta variable no puede serlo. Revisá la columna de origen."

    m = re.match(r"valor ([\d.]+) es una fracción entre 0 y 1", motivo)
    if m:
        return (
            f"\"{nombre}\" dio {m.group(1)} — un número entre 0 y 1, típico de una "
            f"columna de PORCENTAJE, no de cantidad. Es probable que se haya tomado "
            f"la columna de tasa en vez de la de conteo."
        )

    m = re.match(r"'(\w+)' es una variable interna \(la calcula el sistema, nunca viene "
                 r"de un archivo migrado\) pero llegó de fuente '([^']+)'", motivo)
    if m:
        return (
            f"\"{nombre_humano(m.group(1))}\" la calcula el sistema — no debería venir "
            f"de un archivo migrado ({m.group(2)}). Se ignora ese valor, no afecta nada."
        )

    m = re.match(r"(\w+)=([\d.]+) no puede ser mayor que (\w+)=([\d.]+) "
                 r"\(con (\d+)% de tolerancia por desalineación de período\)", motivo)
    if m:
        menor, v_menor, mayor, v_mayor, margen = m.groups()
        return (
            f"\"{nombre_humano(menor)}\" ({_fmt(float(v_menor))}) no puede ser más que "
            f"\"{nombre_humano(mayor)}\" ({_fmt(float(v_mayor))}) — el primero es una "
            f"parte del segundo. Alguno de los dos números está mal, o vienen de "
            f"meses distintos (se permite hasta {margen}% de diferencia por eso)."
        )

    return motivo  # patrón no reconocido: se muestra el motivo técnico tal cual


# ---------------------------------------------------------------------------
# Derivadas — derivacion.py
# ---------------------------------------------------------------------------

def explicar_derivada(d: dict) -> str:
    """`d`: una fila de resultado["variables_derivadas"] —
    variable/valor/kpi_id/kpi_nombre/desde_denominador/tasa_declarada."""
    nombre = nombre_humano(d["variable"])
    kpi_nombre = d.get("kpi_nombre") or f"KPI {d['kpi_id']}"
    return (
        f"\"{nombre}\" no venía como columna en ningún archivo, pero la planilla sí "
        f"traía la tasa de \"{kpi_nombre}\" ({_fmt(d['tasa_declarada'])}%) al lado de "
        f"\"{nombre_humano(d['desde_denominador'])}\" — el sistema despejó el número "
        f"({_fmt(d['valor'])}) a partir de esos dos datos. Se muestra como sugerencia "
        f"a confirmar, no como un dato medido."
    )


# ---------------------------------------------------------------------------
# Discrepancias — reconciliacion.py (misma info que ya llega en "discrepancia")
# ---------------------------------------------------------------------------

def explicar_discrepancia(d: dict) -> str:
    """`d`: una fila de resultado["discrepancias_reconciliacion"] —
    kpi_id/kpi_nombre/calculado/declarado/variables."""
    variables_legibles = ", ".join(f"\"{nombre_humano(v)}\"" for v in d.get("variables", []))
    return (
        f"Para \"{d['kpi_nombre']}\", la planilla declara {_fmt(d['declarado'])}% pero "
        f"con los datos extraídos ({variables_legibles}) el sistema calcula "
        f"{_fmt(d['calculado'])}%. La diferencia es mayor a la tolerancia esperada — "
        f"conviene revisar esas columnas."
    )
