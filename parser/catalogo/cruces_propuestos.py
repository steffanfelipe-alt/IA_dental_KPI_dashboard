"""
cruces_propuestos.py

Fase C del plan de evolución — capa 3 del diseño de cruces (ver `cruces.py`
para las capas 1 y 2, ambas deterministas y sin API). El modelo PROPONE
qué cruces podrían valer la pena entre las variables ya presentes — nunca
calcula el número, nunca declara una unidad que el código no pueda
verificar de forma independiente. Cada propuesta pasa por los mismos
validadores que ya usan las capas 1/2 (`schema.OPERACIONES_LEGALES`,
`schema.ETAPAS_EMBUDO`, `cruces.calcular_cruce` para la intersección de
períodos y la aritmética) antes de aceptarse — el modelo nunca calcula
nada, sólo sugiere qué cruzar y por qué le importa al negocio.

Separado de `cruces.py` a propósito: ese módulo no importa `anthropic` y
tiene que seguir así — importable y testeable sin red, sin arriesgar una
llamada a la API por accidente al generar los cruces de las capas 1/2.
Este módulo SÍ depende de la API y es el único punto de entrada de la
capa 3.

Confianza tope, no calculada: una relación que PROPONE un modelo es
estructuralmente menos cierta que una que el embudo o el álgebra de
unidades declaran por construcción — CONFIANZA_PROPUESTA es el mismo
techo que ya usa `derivacion.CONFIANZA_DERIVADA` (0.6, por debajo de 0.7,
así cae en "a confirmar" y nunca se presenta como dato duro).
"""

import json
from dataclasses import replace
from typing import Optional

from parser.catalogo.catalogo_tecnologico import INTERVENCIONES
from parser.catalogo.cruces import Cruce, calcular_cruce, _nombre_humano
from parser.vocabulario.puerto_llm import PuertoLLM
from parser.vocabulario.schema import ETAPAS_EMBUDO, METRICAS, OPERACIONES_LEGALES, VARIABLE_TYPES

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


MODEL = "claude-sonnet-5"
CONFIANZA_PROPUESTA = 0.6  # mismo techo que derivacion.CONFIANZA_DERIVADA
MAX_PROPUESTAS = 8

_OPERACIONES_VALIDAS = {"/", "-"}

SYSTEM_PROMPT_BASE = """Sos un analista que propone métricas cruzadas para
una clínica dental odontológica, a partir de variables que ya están
cargadas. Nunca calculás ningún valor — el código hace toda la
aritmética — tu trabajo es sólo decir QUÉ dos variables cruzar, con qué
operación, y por qué le importaría al dueño de la clínica.

Reglas:
- Proponé sólo pares cuya combinación tenga sentido de negocio real para
  una clínica dental — nunca un cruce sólo porque las unidades calzan.
  Priorizá lo que conecte con los objetivos de negocio del catálogo que
  te paso abajo.
- "operacion" es "/" o "-", nunca otra cosa.
- "unidad_esperada" es la unidad que ESPERÁS que dé el resultado — el
  código la verifica de forma independiente contra la unidad real de cada
  variable; si no coincide, se descarta tu propuesta entera. No inventes
  una unidad que no tenga sentido dimensional (ej. nunca declares "%"
  para restar dos montos).
- "etapa_embudo": en 1 frase corta, qué etapa (o etapas) del recorrido del
  paciente por la clínica describe este cruce — usá los nombres del
  embudo si aplican (consultas nuevas, turnos agendados, turnos
  asistidos, presupuestos emitidos/aceptados, tratamientos
  iniciados/completados, alta) o "financiero"/"retención" si el cruce cae
  fuera del embudo.
- "como_ayuda_decision": en 1-2 frases, qué decisión concreta del dueño de
  la clínica se vuelve más fácil de tomar con este número (ej. "si esto
  baja de X%, conviene revisar el guion de presupuestación antes de
  invertir más en marketing").
- Máximo 8 propuestas. Mejor pocas y relevantes que muchas genéricas.
- NUNCA devuelvas un número — sólo la estructura de la propuesta.

Devolvé SOLO JSON, sin texto adicional:
{"propuestas": [
  {"variable_a": "...", "operacion": "/", "variable_b": "...",
   "unidad_esperada": "...", "etapa_embudo": "...", "como_ayuda_decision": "..."}
]}
"""


def _payload_variables(variables: dict) -> dict:
    """Sólo variables con serie histórica — sin eso ningún cruce puede
    juntar los 2 períodos comunes que exige `calcular_cruce`, así que
    mostrárselas al modelo sólo gastaría tokens en propuestas que la
    validación va a descartar de entrada."""
    return {
        v: {
            "nombre": METRICAS[v].nombre_humano,
            "definicion": METRICAS[v].definicion,
            "unidad": METRICAS[v].unidad_dato,
            "no_confundir_con": METRICAS[v].no_confundir_con or None,
            "periodos_disponibles": len(vv.serie),
        }
        for v, vv in variables.items()
        if vv.serie and v in METRICAS and VARIABLE_TYPES.get(v) in ("int", "float")
    }


def _objetivos_catalogo() -> list[str]:
    return sorted({i.metrica_objetivo for i in INTERVENCIONES if i.metrica_objetivo})


def _es_conteo_conteo_valido_en_embudo(var_a: str, var_b: str) -> bool:
    """Mismo criterio que `cruces.generar_cruces_embudo`: conteo÷conteo
    sólo es legítimo si ambas están en el embudo declarado Y respetan su
    orden (a = etapa posterior, b = etapa anterior)."""
    if var_a not in ETAPAS_EMBUDO or var_b not in ETAPAS_EMBUDO:
        return False
    return ETAPAS_EMBUDO.index(var_a) > ETAPAS_EMBUDO.index(var_b)


def _validar_propuesta(propuesta: dict, variables: dict) -> Optional[tuple[str, str, str, str]]:
    """None si la propuesta se rechaza; si no, (var_a, operacion, var_b,
    unidad_real) ya verificados contra `schema.py` — nunca contra lo que
    el modelo dijo. Cada rechazo es silencioso acá (se descarta, no
    rompe el batch de propuestas) porque una propuesta mala del modelo no
    puede tirar abajo las demás."""
    var_a = propuesta.get("variable_a")
    operacion = propuesta.get("operacion")
    var_b = propuesta.get("variable_b")

    if operacion not in _OPERACIONES_VALIDAS:
        return None
    # "inexistente o en cuarentena": una variable en cuarentena nunca
    # llega a este dict (pipeline.py la filtra antes) — el mismo chequeo
    # cubre ambos casos.
    if var_a not in variables or var_b not in variables:
        return None
    if var_a not in METRICAS or var_b not in METRICAS:
        return None

    unidad_a = METRICAS[var_a].unidad_dato
    unidad_b = METRICAS[var_b].unidad_dato
    unidad_real = OPERACIONES_LEGALES.get((unidad_a, operacion, unidad_b))
    if unidad_real is None:
        return None  # combinación dimensionalmente ilegal

    if (unidad_a, operacion, unidad_b) == ("conteo", "/", "conteo"):
        if not _es_conteo_conteo_valido_en_embudo(var_a, var_b):
            return None  # conteo÷conteo fuera del embudo: exclusivo de la capa 1

    if propuesta.get("unidad_esperada") != unidad_real:
        # El modelo declaró una unidad que no coincide con la que da el
        # álgebra real — señal de que malentendió la relación. Mismo
        # principio que reconciliacion.py: nunca confiar en lo declarado
        # sin cruzarlo contra lo calculado.
        return None

    return var_a, operacion, var_b, unidad_real


_SIN_ETAPA = "(el modelo no especificó una etapa)"
_SIN_IMPACTO = "(el modelo no explicó el impacto en la decisión)"


def _texto(valor, default: str) -> str:
    """El JSON del modelo puede traer `null` (o directamente un número) en
    un campo de prosa. Coaccionar en vez de explotar: un `.strip()` sobre
    None tiraría abajo el lote ENTERO de propuestas, no sólo la mal
    formada — mismo principio que `_validar_propuesta`, donde cada rechazo
    es silencioso y local."""
    if not isinstance(valor, str):
        return default
    return valor.strip() or default


def _construir_cruce_propuesto(
    var_a: str, operacion: str, var_b: str, unidad: str,
    variables: dict, etapa_embudo, como_ayuda_decision,
) -> Optional[Cruce]:
    """Prosa incompleta del modelo no es motivo para tirar una propuesta
    dimensionalmente válida — si falta alguno de los dos campos
    explicativos, se usa un placeholder en vez de descartarla."""
    nombre = f"{_nombre_humano(var_a)} {'÷' if operacion == '/' else '−'} {_nombre_humano(var_b)}"
    etapa_embudo = _texto(etapa_embudo, _SIN_ETAPA)
    como_ayuda_decision = _texto(como_ayuda_decision, _SIN_IMPACTO)
    cruce = calcular_cruce(
        nombre=nombre, var_a=var_a, operacion=operacion, var_b=var_b, unidad=unidad,
        vv_a=variables[var_a], vv_b=variables[var_b], origen="propuesto",
        justificacion=f"Propuesto por el modelo. Etapa: {etapa_embudo}. Cómo ayuda a decidir: {como_ayuda_decision}",
    )
    if cruce is None:
        return None
    # Techo de confianza (ver docstring del módulo) + los dos campos
    # explicativos que sólo esta capa produce — la capa 1/2 los deja en
    # "" por default (ver dataclass Cruce en cruces.py).
    return replace(
        cruce, confianza=round(min(cruce.confianza, CONFIANZA_PROPUESTA), 4),
        etapa_embudo=etapa_embudo, impacto_decision=como_ayuda_decision,
    )


def proponer_cruces(variables: dict, puerto: Optional[PuertoLLM] = None) -> list[Cruce]:
    """Pide al modelo una lista de cruces candidatos y devuelve sólo los
    que pasan la validación determinista — nunca lo que el modelo haya
    calculado (no calcula nada) ni lo que haya declarado sin verificar.

    `puerto=None` (default, sin puerto configurado) devuelve lista vacía —
    mismo comportamiento de "esta capa simplemente no corrió" que
    `interpretacion.py` usa para sus tres entry points.

    `puerto` (deuda-panel-sistemas-puertollm, U1): antes `client` crudo de
    Anthropic. Esta función no necesita la señal de truncamiento (una
    propuesta cortada a la mitad no parsea como JSON válido y ya se
    descarta más abajo con el mismo trato que un JSON malformado), así que
    habla contra `PuertoLLM.preguntar` — no hace falta el método con
    truncamiento que sí usan `interpretar_kpi`/`interpretar_panel`."""
    if puerto is None:
        return []

    payload_variables = _payload_variables(variables)
    if len(payload_variables) < 2:
        return []  # no hay con qué cruzar

    texto = puerto.preguntar(
        model=MODEL,
        max_tokens=2000,
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT_BASE,
        messages=[{
            "role": "user",
            "content": json.dumps({
                "variables_disponibles": payload_variables,
                "objetivos_de_negocio_del_catalogo": _objetivos_catalogo(),
            }, ensure_ascii=False, default=str),
        }],
    ).strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1].removeprefix("json").strip()

    try:
        payload = json.loads(texto)
    except json.JSONDecodeError:
        # JSON malformado no puede tirar abajo el pipeline — se trata
        # igual que "el modelo no propuso nada esta vez".
        return []

    cruces: list[Cruce] = []
    for propuesta in (payload.get("propuestas") or [])[:MAX_PROPUESTAS]:
        if not isinstance(propuesta, dict):
            continue
        validado = _validar_propuesta(propuesta, variables)
        if validado is None:
            continue
        var_a, operacion, var_b, unidad = validado
        cruce = _construir_cruce_propuesto(
            var_a, operacion, var_b, unidad, variables,
            propuesta.get("etapa_embudo", ""), propuesta.get("como_ayuda_decision", ""),
        )
        if cruce is not None:
            cruces.append(cruce)

    return cruces
