"""
claude_utils.py

Helpers compartidos para leer respuestas de la API de Claude.
"""


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
