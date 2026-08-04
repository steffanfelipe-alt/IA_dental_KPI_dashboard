"""
periodos.py

Fase 1 del plan de evolución. Cierra un hueco silencioso de
`coverage._calcular_serie_kpi`: esa función arma la serie de un KPI
intersectando las series de sus variables *por clave de período*. Si un
archivo etiqueta un mes como "Abril 2026" y otro como "2026-04", la
intersección da vacía y la serie del KPI se cae a `None` sin ningún
aviso — justo el dato que `interpretacion.py` usa para ponderar benchmark
externo vs. historial propio (`peso_benchmark_vs_historial`).

`normalizar_periodo` resuelve toda etiqueta de período a una clave
canónica ("2026-04" para mes, "2026-W18" para semana) para que dos
archivos que describen el mismo mes de formas distintas sí intersecten.

También implementa el date binning que pide el punto 2 del doc de
deficiencias (agrupar registros con fecha + valor en el mismo período
antes de agregar cualquier cosa) — `agrupar_por_periodo`.

Nunca inventa un período: una etiqueta que no se puede interpretar
devuelve `None` (`normalizar_periodo`) o cae en la clave `None` de
`agrupar_por_periodo`, visible para quien llama, no descartada en
silencio.
"""

import re
from datetime import date
from typing import Optional

MESES_ES = {
    "enero": 1, "ene": 1,
    "febrero": 2, "feb": 2,
    "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "jun": 6,
    "julio": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "septiembre": 9, "setiembre": 9, "sep": 9, "sept": 9,
    "octubre": 10, "oct": 10,
    "noviembre": 11, "nov": 11,
    "diciembre": 12, "dic": 12,
}


def _normalizar_anio(anio_txt: str) -> int:
    anio = int(anio_txt)
    # Un año de 2 dígitos en este sistema siempre es 20xx — todas las
    # clínicas que usan PyME OS / Agencia IA operan en el presente, nunca
    # hay un caso real de 19xx que desambiguar.
    return anio + 2000 if anio < 100 else anio


def _fecha_desde_etiqueta(etiqueta: str) -> Optional[date]:
    """Interpreta una etiqueta de período como una fecha concreta. El día
    es arbitrario cuando la etiqueta no lo trae (solo importa para derivar
    año/mes o año/semana) — se usa el día 1 del mes en ese caso."""
    s = etiqueta.strip().lower()
    if not s:
        return None

    # Una fecha (cualquiera de los tres formatos de abajo) puede venir con
    # hora pegada atrás — "2026-04-15 14:30:00", "2026-04-15T14:30" — como
    # la trae un export crudo de un sistema real (timestamp de fila, no una
    # etiqueta de período tipeada a mano). La hora no aporta nada a la
    # granularidad de mes/semana que esta función resuelve, así que se
    # descarta, no se rechaza la fecha entera por su presencia.
    _HORA_OPCIONAL = r"(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?"

    # Ya canónico o casi: "2026-04" o una fecha completa "2026-04-15".
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?" + _HORA_OPCIONAL, s)
    if m:
        anio, mes = int(m.group(1)), int(m.group(2))
        dia = int(m.group(3)) if m.group(3) else 1
        try:
            return date(anio, mes, dia)
        except ValueError:
            return None

    # "Abril 2026", "abr-26", "abr 26", "abril de 2026"
    m = re.fullmatch(r"([a-zñ]+)(?:\s+de)?[\s\-]+(\d{2,4})", s)
    if m:
        mes = MESES_ES.get(m.group(1))
        if mes:
            try:
                return date(_normalizar_anio(m.group(2)), mes, 1)
            except ValueError:
                return None

    # "2-5-25", "30-04-26", "2/5/2025" — día-mes-año, convención Argentina.
    # NUNCA se interpreta como mes-día (mm-dd-aa): una planilla armada por
    # una clínica argentina usa el formato local, y adivinar mal acá
    # confundiría meses silenciosamente en cualquier fecha con día <= 12.
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})" + _HORA_OPCIONAL, s)
    if m:
        dia, mes = int(m.group(1)), int(m.group(2))
        try:
            return date(_normalizar_anio(m.group(3)), mes, dia)
        except ValueError:
            return None

    return None


def normalizar_periodo(etiqueta: str, granularidad: str = "mes") -> Optional[str]:
    """Etiqueta cruda -> clave canónica. `granularidad`: "mes" -> "2026-04",
    "semana" -> "2026-W18" (semana ISO). None si no se pudo interpretar —
    nunca se inventa un período a partir de una etiqueta irreconocible."""
    fecha = _fecha_desde_etiqueta(str(etiqueta))
    if fecha is None:
        return None
    if granularidad == "semana":
        anio_iso, semana_iso, _ = fecha.isocalendar()
        return f"{anio_iso:04d}-W{semana_iso:02d}"
    return f"{fecha.year:04d}-{fecha.month:02d}"


_CANONICO = re.compile(r"\d{4}-(?:\d{2}|W\d{2})")


def es_canonico(clave: str) -> bool:
    """¿`clave` tiene la forma que produce `normalizar_periodo` ("2026-04",
    "2026-W18")? Predicado explícito para que quien construye una serie
    pueda rechazar una etiqueta que NO es un período antes de meterla —
    en vez de depender de que el orden alfabético la deje en un lugar
    inofensivo. Bug real: la fila de nota al pie de una hoja entraba a la
    serie como si fuera un período, y como 'P' ordena después de '2' en
    ASCII quedaba última, o sea elegida como el valor vigente."""
    return bool(_CANONICO.fullmatch(str(clave)))


def orden_cronologico(periodos) -> list[str]:
    """Las claves canónicas ("2026-04", "2026-W18") ordenan cronológicamente
    con un sort de string plano — están todas zero-padded a propósito.

    PRECONDICIÓN: todas las claves son canónicas. Esta función no puede
    ubicar una etiqueta que no es un período (¿va antes o después de
    "2026-04"? no hay respuesta correcta), así que no lo intenta: filtrar
    es responsabilidad de quien arma la serie, con `es_canonico`."""
    return sorted(periodos)


def agrupar_por_periodo(
    registros: list[dict], campo_fecha: str = "fecha", granularidad: str = "mes",
) -> dict[Optional[str], list[dict]]:
    """Date binning (punto 2 del doc de deficiencias): agrupa registros que
    traen un campo de fecha en el mismo período canónico, antes de que
    cualquier otra función los agregue. Un registro cuya fecha no se pudo
    interpretar cae en la clave `None` — visible para auditar, nunca
    descartado en silencio.

    Sin uso todavía (2026-07): su consumidor previsto es el camino de
    `ledger.py` (Fase 2, `construir_ledger_pacientes`), que agrupa eventos
    de paciente ya extraídos como `list[dict]` — no un DataFrame de pandas.
    NO es el arreglo del bug de binning mensual de
    `extractors.excel_parser._construir_serie_periodo`: ese opera sobre un
    DataFrame y se corrigió ahí directamente (normalizar antes de agrupar
    con `groupby`), no reusando esta función. No borrar: cablear el ledger
    es trabajo pendiente, no descartado."""
    grupos: dict[Optional[str], list[dict]] = {}
    for registro in registros:
        etiqueta = registro.get(campo_fecha)
        periodo = normalizar_periodo(str(etiqueta), granularidad) if etiqueta is not None else None
        grupos.setdefault(periodo, []).append(registro)
    return grupos
