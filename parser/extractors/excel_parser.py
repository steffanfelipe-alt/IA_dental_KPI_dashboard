"""
extractors/excel_parser.py

Un Excel de una clínica real casi nunca tiene columnas prolijas. Puede decir
"Monto", "Importe", "Total", o "$" para lo mismo; puede tener "Presupuesto"
y "Presup." en la misma planilla si lo cargó gente distinta. Este módulo no
intenta adivinar con reglas fijas (if columna == "monto") porque se rompe
con la primera clínica que use otro nombre. En cambio:

  1. pandas lee la estructura (hojas, columnas, tipos, primeras filas)
  2. Claude ve los encabezados + una muestra de filas y devuelve el mapeo
     semántico contra el vocabulario de variables de schema.py
  3. Se aplica el mapeo y se agregan/normalizan los valores

El resultado son VariableValue con fuente="migracion_excel" y una
confianza que baja si Claude no está seguro del mapeo de una columna.
"""

import json
from typing import Optional

import pandas as pd

from schema import VARIABLE_TYPES
from coverage import VariableValue

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = f"""Sos un normalizador de datos para clínicas dentales argentinas.
Te paso los encabezados de columnas de un Excel/CSV subido por el dueño de
una clínica, más 3-5 filas de ejemplo. Tu trabajo es mapear cada columna a
UNA de estas variables (o null si ninguna aplica):

{json.dumps(list(VARIABLE_TYPES.keys()), ensure_ascii=False, indent=2)}

Reglas:
- Una columna de fecha de turno + estado ("asistió"/"no show") normalmente
  te da tanto "turnos_agendados" (conteo de filas) como "no_shows" (conteo
  de filas con estado ausente) — indicalo como dos reglas de agregación.
- Si una columna es ambigua entre dos variables (ej: "Monto" podría ser
  monto_presupuestos_aceptados o monto_cobrado), elegí la más probable según
  el contexto de las otras columnas y bajá la confianza a 0.5 o menos.
- Nunca inventes una variable que no está en la lista.
- Devolvé SOLO JSON, sin texto adicional, con este formato exacto:

{{
  "mapeo": [
    {{"columna_original": "...", "variable": "...", "agregacion": "sum|count|count_where|avg",
      "condicion": "opcional, ej. estado == 'no show'", "confianza": 0.0-1.0}}
  ],
  "columnas_sin_mapeo": ["..."]
}}
"""


def leer_estructura(path: str) -> dict:
    """Lee el archivo y arma el resumen que Claude necesita para mapear columnas."""
    if path.endswith(".csv"):
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path, sheet_name=0)

    return {
        "columnas": list(df.columns),
        "muestra_filas": df.head(5).to_dict(orient="records"),
        "cantidad_filas": len(df),
        "_df": df,  # se descarta antes de mandarlo a Claude, se usa después para aplicar el mapeo
    }


def pedir_mapeo_a_claude(estructura: dict, client) -> dict:
    payload = {
        "columnas": estructura["columnas"],
        "muestra_filas": estructura["muestra_filas"],
        "cantidad_filas": estructura["cantidad_filas"],
    }
    respuesta = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
    )
    texto = respuesta.content[0].text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1].removeprefix("json").strip()
    return json.loads(texto)


def aplicar_mapeo(df: pd.DataFrame, mapeo: dict) -> dict[str, VariableValue]:
    variables: dict[str, VariableValue] = {}

    for regla in mapeo["mapeo"]:
        col = regla["columna_original"]
        var = regla["variable"]
        if var is None or col not in df.columns:
            continue

        serie = df[col]
        if regla.get("condicion"):
            try:
                serie = df.query(regla["condicion"])[col]
            except Exception:
                pass  # condición no aplicable con pandas.query, se ignora esa regla puntual

        agregacion = regla.get("agregacion", "sum")
        if agregacion == "sum":
            valor = float(serie.sum())
        elif agregacion == "count":
            valor = int(serie.count())
        elif agregacion == "count_where":
            valor = int(len(serie))
        elif agregacion == "avg":
            valor = float(serie.mean())
        else:
            continue

        # Si dos columnas mapean a la misma variable, se prioriza mayor confianza.
        nueva = VariableValue(valor=valor, fuente="migracion_excel", confianza=regla.get("confianza", 0.8))
        existente = variables.get(var)
        if existente is None or nueva.confianza > existente.confianza:
            variables[var] = nueva

    return variables


def parsear_excel(path: str, client: Optional["anthropic.Anthropic"] = None) -> dict[str, VariableValue]:
    if client is None:
        assert anthropic is not None, "Instalar el SDK: pip install anthropic --break-system-packages"
        client = anthropic.Anthropic()

    estructura = leer_estructura(path)
    df = estructura.pop("_df")
    mapeo = pedir_mapeo_a_claude(estructura, client)
    return aplicar_mapeo(df, mapeo)
