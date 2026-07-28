"""
claude_utils.py

Helpers compartidos para leer respuestas de la API de Claude.
"""


def extraer_texto(respuesta) -> str:
    """
    Primer bloque de tipo "text" de una respuesta de Claude.

    No asumir que el texto está en content[0]: con thinking activado (por
    defecto en algunos modelos, sin que el caller lo pida explícitamente),
    la respuesta trae uno o más ThinkingBlock antes del bloque de texto real.
    """
    for bloque in respuesta.content:
        if bloque.type == "text":
            return bloque.text
    raise ValueError(
        f"La respuesta de Claude no tiene ningún bloque de texto "
        f"(stop_reason={respuesta.stop_reason!r})."
    )
