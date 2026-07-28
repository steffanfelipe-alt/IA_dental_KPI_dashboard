"""
extractors/excel_parser.py

Un Excel de una clínica real casi nunca tiene columnas prolijas, ni una
sola hoja útil, ni el encabezado en la fila 0. Puede decir "Monto",
"Importe", "Total", o "$" para lo mismo; puede tener 3 hojas con datos
distintos (embudo, financiero, operativo); puede tener una fila de título
y una fila en blanco antes del encabezado real. Este módulo no intenta
adivinar con reglas fijas porque se rompe con la primera clínica que arme
su planilla distinto. En cambio:

  1. pandas lee cada hoja del archivo en crudo (sin asumir dónde está el
     encabezado) y arma una vista previa de sus primeras filas.
  2. Claude ve esa vista cruda de todas las hojas y devuelve, por hoja,
     cuál fila es el encabezado real y el mapeo semántico de cada columna
     (por posición, no por nombre) contra el vocabulario de schema.py.
  3. Con la fila de encabezado ya identificada, se vuelve a leer cada hoja
     bien formada y se aplica el mapeo: se agregan/normalizan los valores.

El resultado son VariableValue con fuente="migracion_excel" (o
"migracion_excel:<hoja>" cuando el archivo tiene más de una hoja) y una
confianza que baja si Claude no está seguro del mapeo de una columna.
"""

import json
from typing import Optional

import pandas as pd

from schema import VARIABLE_TYPES
from coverage import VariableValue
from claude_utils import extraer_texto

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


MODEL = "claude-sonnet-5"
FILAS_PREVIEW = 10

SYSTEM_PROMPT = f"""Sos un normalizador de datos para clínicas dentales argentinas.
Te paso, por cada hoja de un Excel (o la única hoja implícita de un CSV),
una vista cruda de sus primeras {FILAS_PREVIEW} filas — SIN asumir dónde
está el encabezado: es común que haya una fila de título y una fila vacía
antes de la fila real de nombres de columna (reportes armados a mano).

Tu trabajo, por cada hoja:

1. Identificar el índice (0-based) de la fila que contiene los nombres de
   columna reales. Si la hoja no tiene una tabla reconocible, devolvé
   "fila_encabezado": null y "mapeo": [].
2. Mapear cada columna (por su índice, NO por nombre) a UNA de estas
   variables (o null si ninguna aplica):

{json.dumps(list(VARIABLE_TYPES.keys()), ensure_ascii=False, indent=2)}

Aclaración sobre una variable fácil de confundir:
- "tiempo_respuesta_promedio_min" es cuánto tarda LA CLÍNICA en responder
  a una consulta/lead NUEVO (primer contacto — WhatsApp, teléfono, etc.),
  en MINUTOS. NO es cuánto tarda un paciente en aceptar o rechazar un
  presupuesto ya enviado — eso es un dato distinto que hoy no tiene
  variable en este vocabulario; si encontrás una columna así, dejala sin
  mapear en vez de forzarla acá. Si la fuente da el dato en otra unidad
  (horas, días), convertí el VALOR a minutos vos mismo antes de reportarlo.

Reglas generales:
- Una hoja puede tener datos ya agregados por período (una fila = un mes)
  en vez de datos crudos por transacción — en ese caso "agregacion"
  normalmente es "avg" sobre la columna (promedio de los períodos de la
  muestra), no "sum".
- Una columna de fecha de turno + estado ("asistió"/"no show") normalmente
  te da tanto "turnos_agendados" (conteo de filas) como "no_shows" (conteo
  de filas con estado ausente) — indicalo como dos reglas de agregación,
  con "condicion" referenciando el nombre real de columna (el texto que
  identificaste en la fila de encabezado, no el índice).
- Si una columna es ambigua entre dos variables, elegí la más probable
  según el contexto de las otras columnas y bajá la confianza a 0.5 o menos.
- Nunca inventes una variable que no está en la lista.
- Devolvé SOLO JSON, sin texto adicional, con este formato exacto:

{{
  "hojas": [
    {{
      "hoja": "nombre de la hoja tal cual te la pasé (o null si es un CSV)",
      "fila_encabezado": 0,
      "mapeo": [
        {{"columna_index": 0, "variable": "...", "agregacion": "sum|count|count_where|avg",
          "condicion": "opcional, ej. estado == 'no show'", "confianza": 0.0-1.0}}
      ],
      "columnas_sin_mapeo": [1, 3]
    }}
  ]
}}
"""


def _grid_serializable(df: pd.DataFrame) -> list[list]:
    return df.where(pd.notnull(df), None).values.tolist()


def leer_hojas_crudas(path: str) -> list[dict]:
    """Vista previa cruda (sin asumir encabezado) de cada hoja del archivo."""
    if path.endswith(".csv"):
        df = pd.read_csv(path, header=None, nrows=FILAS_PREVIEW)
        return [{"hoja": None, "grid": _grid_serializable(df)}]

    hojas = []
    excel = pd.ExcelFile(path)
    for nombre in excel.sheet_names:
        df = excel.parse(nombre, header=None, nrows=FILAS_PREVIEW)
        hojas.append({"hoja": nombre, "grid": _grid_serializable(df)})
    return hojas


def pedir_mapeo_a_claude(hojas_crudas: list[dict], client) -> dict:
    respuesta = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": json.dumps({"hojas": hojas_crudas}, ensure_ascii=False, default=str),
        }],
    )
    texto = extraer_texto(respuesta).strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1].removeprefix("json").strip()
    return json.loads(texto)


def _releer_con_encabezado(path: str, hoja: Optional[str], fila_encabezado: int) -> pd.DataFrame:
    if path.endswith(".csv"):
        return pd.read_csv(path, header=fila_encabezado)
    return pd.read_excel(path, sheet_name=hoja, header=fila_encabezado)


def aplicar_mapeo(
    df: pd.DataFrame,
    mapeo_hoja: dict,
    variables: Optional[dict[str, VariableValue]] = None,
) -> dict[str, VariableValue]:
    variables = dict(variables) if variables else {}
    hoja = mapeo_hoja.get("hoja")
    fuente = f"migracion_excel:{hoja}" if hoja else "migracion_excel"

    for regla in mapeo_hoja["mapeo"]:
        idx = regla.get("columna_index")
        var = regla["variable"]
        if var is None or idx is None or idx >= len(df.columns):
            continue
        col = df.columns[idx]

        serie = df[col]
        if regla.get("condicion"):
            try:
                serie = df.query(regla["condicion"])[col]
            except Exception:
                pass  # condición no aplicable con pandas.query, se ignora esa regla puntual

        agregacion = regla.get("agregacion", "sum")
        if agregacion == "sum":
            valor = float(pd.to_numeric(serie, errors="coerce").sum())
        elif agregacion == "count":
            valor = int(serie.count())
        elif agregacion == "count_where":
            valor = int(len(serie))
        elif agregacion == "avg":
            valor = float(pd.to_numeric(serie, errors="coerce").mean())
        else:
            continue

        # Si dos columnas (de la misma hoja o de hojas distintas) mapean a
        # la misma variable, se prioriza la de mayor confianza.
        nueva = VariableValue(valor=valor, fuente=fuente, confianza=regla.get("confianza", 0.8))
        existente = variables.get(var)
        if existente is None or nueva.confianza > existente.confianza:
            variables[var] = nueva

    return variables


def parsear_excel(path: str, client: Optional["anthropic.Anthropic"] = None) -> dict[str, VariableValue]:
    if client is None:
        assert anthropic is not None, "Instalar el SDK: pip install anthropic --break-system-packages"
        client = anthropic.Anthropic()

    hojas_crudas = leer_hojas_crudas(path)
    respuesta = pedir_mapeo_a_claude(hojas_crudas, client)

    variables: dict[str, VariableValue] = {}
    for mapeo_hoja in respuesta["hojas"]:
        if mapeo_hoja.get("fila_encabezado") is None or not mapeo_hoja.get("mapeo"):
            continue
        df = _releer_con_encabezado(path, mapeo_hoja.get("hoja"), mapeo_hoja["fila_encabezado"])
        variables = aplicar_mapeo(df, mapeo_hoja, variables)

    return variables
