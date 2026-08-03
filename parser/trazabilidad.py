"""
trazabilidad.py

Fase 0 del plan de evolución (deficiencias-parser-kpis.md, punto 2): un KPI
calculado debe poder "explicarse". Hoy `VariableValue.valor` no dice de
dónde salió el número — si un tiempo de respuesta da 390 min, no hay forma
de saber si es "6.5 horas × 60" o un error de mapeo sin volver a correr
todo el pipeline a mano.

Este módulo no cambia ningún valor ya calculado — solo registra, para cada
variable, qué celda(s) del archivo de origen, qué agregación y qué
conversión de unidad se aplicaron para llegar a `.valor`. Es metadata pura:
`Trazabilidad` es opcional en `VariableValue` (default None) y ningún
consumidor existente necesita tocarse para seguir funcionando.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # evita el import circular con coverage.py (VariableValue)
    from coverage import VariableValue


@dataclass
class Trazabilidad:
    """Procedencia de un valor extraído o derivado.

    `celdas_origen` es deliberadamente liviano (no todas las celdas
    individuales de una suma de 200 filas): guarda la referencia a la
    hoja/columna/fila y cuántos registros entraron, suficiente para que un
    humano audite "de dónde salió esto" sin tener que serializar el
    archivo entero en cada variable.

    `origen` distingue de qué tipo de procedencia se trata — no todo valor
    sale de una celda de Excel: `derivacion.py` despeja una variable a
    partir de una tasa que la planilla ya trae calculada (ver
    `no_confundir_con` de ese módulo), y esa procedencia también merece
    quedar explicada, aunque no haya hoja/fila/columna que citar.
    """
    origen: str = "celda"    # "celda" | "derivado_de_tasa"
    hoja: Optional[str] = None
    columna: Optional[str] = None
    fila: Optional[int] = None                 # solo para metricas_en_filas (una sola celda)
    condicion: Optional[str] = None
    agregacion: str = "sum"
    n_registros: Optional[int] = None          # cuántas filas entraron en la agregación
    filas_excluidas: list = field(default_factory=list)
    unidad_origen: Optional[str] = None
    unidad_final: Optional[str] = None
    factor_conversion: Optional[float] = None
    valor_pre_conversion: Any = None
    valor_final: Any = None
    detalle: Optional[str] = None              # texto libre para orígenes que no son una celda


def _fuente_legible(t: Trazabilidad) -> str:
    partes = []
    if t.hoja:
        partes.append(f"hoja '{t.hoja}'")
    if t.fila is not None:
        partes.append(f"fila {t.fila}")
    if t.columna:
        partes.append(f"columna '{t.columna}'")
    if t.condicion:
        partes.append(f"condición '{t.condicion}'")
    return ", ".join(partes) if partes else "origen no registrado"


def explicar(vv: "VariableValue") -> str:
    """Texto legible de cómo se llegó a `vv.valor`, para mostrar en el
    runner manual o en un futuro endpoint de auditoría.

    Si `vv.trazabilidad` es None (variable de wizard, de visión antes de
    que ese extractor la popule, o derivada — ver derivacion.py) se
    devuelve una explicación degradada en vez de fallar: la ausencia de
    traza es información válida, no un error.
    """
    t = vv.trazabilidad
    if t is None:
        return f"{vv.valor!r} — sin traza registrada (fuente: {vv.fuente})"

    if t.origen == "derivado_de_tasa":
        base = f"{t.valor_final!r} = {t.valor_pre_conversion!r} × {t.factor_conversion} ({t.detalle})"
        return base

    if t.factor_conversion is not None and t.valor_pre_conversion is not None:
        base = (
            f"{t.valor_final!r} = {t.valor_pre_conversion!r} {t.unidad_origen} "
            f"× {t.factor_conversion} ({_fuente_legible(t)})"
        )
    else:
        base = f"{t.valor_final!r} ({_fuente_legible(t)})"

    if t.agregacion == "valor_vigente":
        # Hallazgo #3: este valor es la celda de un solo período (el
        # último de la serie), no una agregación de varios registros.
        base += f" — valor del último período ({vv.periodo})" if vv.periodo else " — valor del último período"
    elif t.n_registros is not None and t.n_registros > 1:
        base += f" — {t.agregacion} de {t.n_registros} registros"
    if t.filas_excluidas:
        base += f" — excluidas {len(t.filas_excluidas)} fila(s) (ej. TOTAL/Promedio)"
    return base
