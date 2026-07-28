"""
extractors/vision_parser.py

Para fotos de cuadernos, planillas impresas, o capturas de pantalla de
otro sistema (agenda vieja, Excel de otra clínica, etc.). A diferencia del
Excel, acá no hay estructura de columnas que leer con pandas — todo el
trabajo de lectura Y de mapeo lo hace Claude Vision en un solo paso.

La confianza que devuelve Claude por cada dato leído es más importante acá
que en el parser de Excel: una foto de cuaderno manuscrito puede tener
números ambiguos (¿es un 7 o un 1?), así que todo lo que declare confianza
baja se muestra en el wizard como sugerencia a confirmar, no como dato final.
"""

import base64
import json
from pathlib import Path
from typing import Optional

from schema import VARIABLE_TYPES
from coverage import VariableValue
from claude_utils import extraer_texto

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = f"""Sos un lector de planillas de clínicas dentales argentinas,
manuscritas o impresas. Te paso una imagen (foto de cuaderno, planilla
impresa, o captura de pantalla de otro sistema). Extraé todos los datos que
puedas y mapealos a estas variables:

{json.dumps(list(VARIABLE_TYPES.keys()), ensure_ascii=False, indent=2)}

Aclaración sobre una variable fácil de confundir:
- "tiempo_respuesta_promedio_min" es cuánto tarda LA CLÍNICA en responder
  a una consulta/lead NUEVO (primer contacto), en MINUTOS. NO es cuánto
  tarda un paciente en aceptar o rechazar un presupuesto ya enviado — eso
  no tiene variable en este vocabulario todavía; si ves un dato así, no lo
  mapees acá. Si la fuente da el dato en otra unidad, convertí el valor a
  minutos antes de reportarlo.

Reglas:
- Si la imagen es una tabla de turnos con columna de asistencia, contá
  turnos_agendados y no_shows por separado.
- Si hay montos escritos a mano y no estás seguro de un dígito, igual
  devolvé tu mejor lectura pero con confianza baja (0.3-0.5).
- Si la imagen no tiene nada relevante a estas variables, devolvé un mapeo
  vacío — no inventes datos.
- Devolvé SOLO JSON, sin texto adicional:

{{
  "variables_encontradas": [
    {{"variable": "...", "valor": <número o valor>, "confianza": 0.0-1.0,
      "nota": "de dónde salió este número en la imagen"}}
  ],
  "descripcion_imagen": "1 línea de qué tipo de documento es"
}}
"""


def _media_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")


def parsear_imagen(path: str, client: Optional["anthropic.Anthropic"] = None) -> dict[str, VariableValue]:
    if client is None:
        assert anthropic is not None, "Instalar el SDK: pip install anthropic --break-system-packages"
        client = anthropic.Anthropic()

    with open(path, "rb") as f:
        imagen_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    respuesta = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": _media_type(path), "data": imagen_b64,
                }},
                {"type": "text", "text": "Extraé los datos de esta planilla."},
            ],
        }],
    )

    texto = extraer_texto(respuesta).strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1].removeprefix("json").strip()
    payload = json.loads(texto)

    variables: dict[str, VariableValue] = {}
    for item in payload.get("variables_encontradas", []):
        var = item["variable"]
        if var not in VARIABLE_TYPES:
            continue  # Claude no debería inventar, pero por las dudas se descarta
        variables[var] = VariableValue(
            valor=item["valor"],
            fuente="migracion_foto",
            confianza=item.get("confianza", 0.6),
        )
    return variables


def parsear_pdf(path: str, client: Optional["anthropic.Anthropic"] = None) -> dict[str, VariableValue]:
    """
    PDFs (export de otro sistema, o facturas escaneadas) se mandan como
    documento nativo — Claude los lee sin necesidad de rasterizar página
    por página primero.
    """
    if client is None:
        assert anthropic is not None, "Instalar el SDK: pip install anthropic --break-system-packages"
        client = anthropic.Anthropic()

    with open(path, "rb") as f:
        pdf_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    respuesta = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {
                    "type": "base64", "media_type": "application/pdf", "data": pdf_b64,
                }},
                {"type": "text", "text": "Extraé los datos de este documento."},
            ],
        }],
    )

    texto = extraer_texto(respuesta).strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1].removeprefix("json").strip()
    payload = json.loads(texto)

    variables: dict[str, VariableValue] = {}
    for item in payload.get("variables_encontradas", []):
        var = item["variable"]
        if var not in VARIABLE_TYPES:
            continue
        variables[var] = VariableValue(
            valor=item["valor"],
            fuente="migracion_foto",
            confianza=item.get("confianza", 0.6),
        )
    return variables
