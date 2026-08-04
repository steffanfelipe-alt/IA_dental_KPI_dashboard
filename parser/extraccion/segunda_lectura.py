"""
segunda_lectura.py

Segunda opinión independiente para variables que reconciliacion.py no
pudo verificar (no hay una tasa declarada al lado en la planilla para
cruzarlas) y que además quedaron con confianza baja. Se le pide a Claude
releer la hoja desde cero, sin ningún contexto del primer mapeo: si
coincide con lo ya extraído sube la confianza; si no, la confianza queda
baja y el dato se muestra como "a confirmar" en vez de elegir en silencio.

Por qué NO renderiza una imagen
-------------------------------
El informe de deficiencias original proponía "mandar la hoja a un modelo
con visión". Al implementarlo se vio que para una planilla eso sería un
RETROCESO, no una mejora: el grid de celdas que ya se manda es **sin
pérdida** (los valores exactos, tal como los guarda el archivo), mientras
que una imagen es una representación más frágil — un modelo puede leer
mal un dígito de una imagen, no de un número que se le pasa literal.
Además haría falta un renderer externo (LibreOffice headless) que no está
instalado.

La brecha real que la idea de "visión" quería cubrir era la estructura
visual que se perdía al aplanar la hoja con pandas. Esa brecha se cerró
por otro lado y de forma determinista: `excel_parser.leer_formatos_columna`
lee con openpyxl el formato de cada celda, y una columna formateada como
porcentaje ya no puede mapearse a una variable de conteo
(`excel_parser._formato_incompatible`). Eso no depende de que ningún
modelo acierte.

Este módulo, entonces, hace lo que su nombre dice: una segunda lectura,
por texto. Se activa solo para variables de baja confianza que la
reconciliación no pudo tocar — así el costo extra queda acotado al caso
ambiguo, no a cada archivo.
"""

import json

from parser.vocabulario.schema import METRICAS
from parser.cobertura_calidad.coverage import VariableValue
from parser.vocabulario.claude_utils import extraer_json_de_texto
from parser.vocabulario.puerto_llm import PuertoLLM
from parser.extraccion import vision_parser

MODEL = "claude-sonnet-5"
UMBRAL_CONFIANZA_BAJA = 0.7

SYSTEM_PROMPT_BASE = """Sos un lector de planillas independiente. Te paso
la vista cruda de una hoja (una lista de filas, cada una una lista de
celdas) y una lista de variables puntuales que necesito que releas de
cero — no sabés nada de cómo se leyó antes, ni tenés que confiar en nada
previo. Por cada variable te doy su definición. Devolvé tu propia lectura
del valor vigente (el período más reciente si la hoja tiene varios), con
tu propia confianza 0-1.

Devolvé SOLO JSON:
{"lecturas": [{"variable": "...", "valor": <número>, "confianza": 0.0-1.0,
  "nota": "de dónde salió este número en la hoja"}]}
"""


def variables_a_verificar(
    variables: dict[str, VariableValue],
    variables_ya_reconciliadas: set[str],
) -> list[str]:
    """
    Filtra qué variables ameritan una segunda lectura: confianza baja Y
    reconciliacion.py no las pudo cruzar contra una tasa declarada (si ya
    las cruzó, esa es una verificación más fuerte que una segunda opinión
    de texto — no hace falta gastar otra llamada).
    """
    return sorted(
        var for var, vv in variables.items()
        if vv.confianza < UMBRAL_CONFIANZA_BAJA and var not in variables_ya_reconciliadas
    )


def pedir_segunda_lectura(
    grid: list[list], variables: list[str], puerto_llm: PuertoLLM,
) -> dict[str, dict]:
    if not variables:
        return {}
    definiciones = {
        v: {"nombre": METRICAS[v].nombre_humano, "definicion": METRICAS[v].definicion}
        for v in variables if v in METRICAS
    }
    texto = puerto_llm.preguntar(
        model=MODEL,
        max_tokens=1500,
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT_BASE,
        messages=[{
            "role": "user",
            "content": json.dumps({"grid": grid, "variables": definiciones}, ensure_ascii=False, default=str),
        }],
    )
    payload = extraer_json_de_texto(texto)
    return {item["variable"]: item for item in payload.get("lecturas", []) if "variable" in item}


def pedir_segunda_lectura_imagen(
    path: str, variables: list[str], puerto_llm: PuertoLLM,
) -> dict[str, dict]:
    """
    Segunda lectura para variables de origen "migracion_foto" (Bug #2). El
    "por qué NO renderiza una imagen" del docstring del módulo es sobre NO
    rasterizar una PLANILLA (ahí el grid sin pérdida es mejor que una
    imagen) — no aplica acá: el origen YA ES una foto/PDF, no hay grid que
    perder, así que releerla con visión es la única segunda opinión
    posible.

    A diferencia de pedir_segunda_lectura (que manda un grid recortado a
    las variables pedidas), acá se manda la imagen ENTERA de nuevo a
    vision_parser.parsear_imagen — una relectura ciega, sin contexto del
    primer mapeo, igual en espíritu a la relectura de Excel. Se descarta
    todo lo que la relectura encuentre que no sea una de las `variables`
    pedidas, y se normaliza al mismo contrato {variable: {variable, valor,
    confianza}} que ya devuelve pedir_segunda_lectura, para que
    contrastar() no necesite saber de qué fuente vino la segunda lectura.
    """
    if not variables:
        return {}
    relectura = vision_parser.parsear_imagen(path, puerto_llm)
    return {
        var: {"variable": var, "valor": vv.valor, "confianza": vv.confianza}
        for var, vv in relectura.items() if var in variables
    }


def contrastar(
    variables: dict[str, VariableValue], lecturas: dict[str, dict], tolerancia_pct: float = 5.0,
) -> tuple[dict[str, float], dict[str, dict]]:
    """
    Compara el valor ya extraído contra la segunda lectura.
    Devuelve (confianza_actualizada, discrepancias) — no decide solo qué
    valor usar cuando discrepan: eso lo resuelve el mecanismo de
    conflictos existente (mismo criterio que dos archivos que no
    coinciden), así el llamador arma un Conflicto con ambos candidatos.
    """
    confianza_actualizada: dict[str, float] = {}
    discrepancias: dict[str, dict] = {}

    for var, lectura in lecturas.items():
        if var not in variables:
            continue
        original = variables[var].valor
        segunda = lectura.get("valor")
        if not isinstance(original, (int, float)) or not isinstance(segunda, (int, float)):
            continue
        coincide = (
            abs(original - segunda) <= abs(original) * tolerancia_pct / 100
            if original else segunda == 0
        )
        if coincide:
            confianza_actualizada[var] = min(1.0, variables[var].confianza + 0.2)
        else:
            discrepancias[var] = {
                "original": original, "segunda_lectura": segunda,
                "confianza_segunda_lectura": lectura.get("confianza", 0.5),
                "nota": lectura.get("nota", ""),
            }

    return confianza_actualizada, discrepancias
