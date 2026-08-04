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

from parser.vocabulario.schema import VARIABLE_TYPES
from parser.cobertura_calidad.coverage import VariableValue
from parser.vocabulario.claude_utils import extraer_json_de_texto
from parser.vocabulario.puerto_llm import AdaptadorAnthropic, PuertoLLM

MODEL = "claude-sonnet-5"

# Mismo criterio que excel_parser.VARIABLES_EXCEL: "list" y "ledger" no son
# variables que una foto pueda mapear con una sola celda (un ledger es
# {paciente_id: [eventos]}, no un número) — sin este filtro el modelo ve
# "ledger_pacientes" en el vocabulario y le asigna un escalar (confirmado
# en la corrida real de H3: mapeó 1240 ahí), que después queda en
# cuarentena por validacion.py. Mejor no ofrecerlo.
_VARIABLES_FOTO = [v for v in VARIABLE_TYPES if VARIABLE_TYPES[v] not in ("list", "ledger")]

SYSTEM_PROMPT = f"""Sos un lector de planillas de clínicas dentales argentinas,
manuscritas o impresas. Te paso una imagen (foto de cuaderno, planilla
impresa, o captura de pantalla de otro sistema). Extraé todos los datos que
puedas y mapealos a estas variables:

{json.dumps(_VARIABLES_FOTO, ensure_ascii=False, indent=2)}

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
- Anclaje de fila (crítico — una planilla con muchas filas es fácil de leer
  un renglón corrida): antes de reportar un valor, fijate en qué fila está
  literalmente impreso o escrito, y devolvé en "etiqueta_fila" el texto de
  la etiqueta que está en esa misma fila (mismo renglón), no la de la fila
  de arriba o abajo. Un corrimiento vertical de una sola fila (ej. leer el
  valor de "reactivados" en la fila de "inactivos_contactados") es el error
  más común y el más difícil de notar — verificá explícitamente que el
  valor y su etiqueta compartan renglón antes de reportarlos. Si hay
  CUALQUIER duda de a qué fila pertenece un valor, devolvé igual tu mejor
  lectura pero con confianza baja (0.3-0.5) y explicá la duda en "nota" —
  no reportes confianza alta cuando la alineación de fila es dudosa.
- Devolvé SOLO JSON, sin texto adicional:

{{
  "variables_encontradas": [
    {{"variable": "...", "valor": <número o valor>, "confianza": 0.0-1.0,
      "etiqueta_fila": "el texto de la etiqueta que está en la MISMA fila que este valor",
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


def parsear_imagen(path: str, puerto_llm: Optional[PuertoLLM] = None) -> dict[str, VariableValue]:
    if puerto_llm is None:
        puerto_llm = AdaptadorAnthropic()

    with open(path, "rb") as f:
        imagen_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    texto = puerto_llm.preguntar(
        model=MODEL,
        max_tokens=2000,
        thinking={"type": "disabled"},
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

    payload = extraer_json_de_texto(texto)

    variables: dict[str, VariableValue] = {}
    for item in payload.get("variables_encontradas", []):
        # Un item mal formado (falta "variable" o "valor") no puede tirar
        # abajo el resto del lote — una foto manuscrita es la entrada con
        # más chances de que el modelo devuelva algo incompleto en una
        # sola fila (mismo principio que cruces_propuestos.py).
        try:
            var = item["variable"]
            valor = item["valor"]
        except (KeyError, TypeError):
            continue
        if var not in VARIABLE_TYPES:
            continue  # Claude no debería inventar, pero por las dudas se descarta
        if VARIABLE_TYPES[var] in ("list", "ledger"):
            continue  # no están en el vocabulario del prompt, pero por las dudas
        variables[var] = VariableValue(
            valor=valor,
            fuente="migracion_foto",
            confianza=item.get("confianza", 0.6),
        )
    return variables


def parsear_pdf(path: str, puerto_llm: Optional[PuertoLLM] = None) -> dict[str, VariableValue]:
    """
    PDFs (export de otro sistema, o facturas escaneadas) se mandan como
    documento nativo — Claude los lee sin necesidad de rasterizar página
    por página primero.
    """
    if puerto_llm is None:
        puerto_llm = AdaptadorAnthropic()

    with open(path, "rb") as f:
        pdf_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    texto = puerto_llm.preguntar(
        model=MODEL,
        max_tokens=2000,
        thinking={"type": "disabled"},
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

    payload = extraer_json_de_texto(texto)

    variables: dict[str, VariableValue] = {}
    for item in payload.get("variables_encontradas", []):
        try:
            var = item["variable"]
            valor = item["valor"]
        except (KeyError, TypeError):
            continue
        if var not in VARIABLE_TYPES:
            continue
        variables[var] = VariableValue(
            valor=valor,
            fuente="migracion_foto",
            confianza=item.get("confianza", 0.6),
        )
    return variables
