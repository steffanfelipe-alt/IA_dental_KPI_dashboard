"""
claude_utils.py

Helpers compartidos para leer respuestas de la API de Claude.
"""

import json


def respuesta_truncada(respuesta) -> bool:
    """¿La respuesta se cortó por `max_tokens` en vez de terminar sola?

    Existe porque el modo de falla silencioso es peor que el ruidoso: un
    informe cortado a la mitad se ve igual que uno completo, y el sistema
    lo presentaría como diagnóstico terminado. Quien llame decide qué
    hacer, pero no puede ignorarlo sin querer.
    """
    return getattr(respuesta, "stop_reason", None) == "max_tokens"


def extraer_texto(respuesta) -> str:
    """
    Primer bloque de tipo "text" de una respuesta de Claude.

    No asumir que el texto está en content[0]: con thinking activado, la
    respuesta trae uno o más ThinkingBlock antes del bloque de texto real.

    OJO con el default de thinking: en los modelos actuales (Sonnet 5,
    Opus 5) omitir el parámetro `thinking` NO significa "sin thinking" —
    corre adaptativo. Y `max_tokens` es un techo sobre thinking + texto,
    así que con un presupuesto ajustado el thinking se lo come entero y
    no queda ningún bloque de texto que devolver. Ese es exactamente el
    caso que este error reporta; la solución está del lado del llamador
    (declarar `thinking` explícitamente o subir `max_tokens`), no acá.
    """
    for bloque in respuesta.content:
        if bloque.type == "text":
            return bloque.text
    if respuesta_truncada(respuesta):
        raise ValueError(
            "La respuesta de Claude se agotó en max_tokens antes de escribir "
            "una sola palabra de texto: el presupuesto de tokens se consumió "
            "entero en el thinking. Declarar `thinking` explícitamente en la "
            "llamada o subir `max_tokens`."
        )
    raise ValueError(
        f"La respuesta de Claude no tiene ningún bloque de texto "
        f"(stop_reason={respuesta.stop_reason!r})."
    )


def extraer_json(respuesta) -> dict:
    """
    Parsea el JSON de una respuesta de Claude que se pidió como "SOLO JSON,
    sin texto adicional".

    Bug real que motiva esto: vision_parser.parsear_imagen asumía que el
    texto entero era ```texto.split("```")[1]``` — un fence ÚNICO que
    arranca en el carácter 0. Con una foto ambigua (letra manuscrita,
    números dudosos) Claude a veces antepone una aclaración antes del
    bloque ("no puedo leer bien un valor, pero mi mejor lectura es:"), o
    no cierra el fence. Ninguno de los dos casos es "el modelo no
    cumplió la instrucción" en un sentido grave — es variación normal de
    un LLM — pero el parseo viejo no toleraba ninguno y explotaba con
    `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`, un
    error que no dice nada de lo que realmente contestó Claude.

    Estrategia, en orden: (1) si hay un fence ``` ```, usar el contenido
    entre el primer y el segundo (o hasta el final si no cierra) en vez
    de exigir que el string entero sea el fence; (2) sacar un prefijo
    "json" si quedó pegado; (3) dentro de ese candidato, recortar entre
    la primera '{' y la última '}' — así un preámbulo o un cierre en
    prosa alrededor del JSON no rompen el parseo. Si después de todo eso
    no hay JSON válido, se levanta ValueError con un recorte del texto
    crudo: el objetivo es que el próximo fallo de este tipo diga QUÉ
    contestó Claude, no un JSONDecodeError pelado sin contexto.
    """
    texto = extraer_texto(respuesta).strip()
    candidato = texto

    if "```" in candidato:
        partes = candidato.split("```")
        candidato = partes[1] if len(partes) > 1 else partes[0]
        candidato = candidato.strip()
        if candidato[:4].lower() == "json":
            candidato = candidato[4:]
        candidato = candidato.strip()

    inicio = candidato.find("{")
    fin = candidato.rfind("}")

    if inicio == -1 or fin == -1 or fin < inicio:
        raise ValueError(
            "No encontré un objeto JSON en la respuesta de Claude. "
            f"Texto crudo recibido (recortado): {texto[:500]!r}"
        )

    candidato = candidato[inicio:fin + 1]

    try:
        return json.loads(candidato)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"La respuesta de Claude no es JSON válido ({e}). "
            f"Texto crudo recibido (recortado): {texto[:500]!r}"
        ) from e
