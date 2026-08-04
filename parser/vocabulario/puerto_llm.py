"""
puerto_llm.py

Puerto (Strategy/Adapter, scope: solo el camino de extracción) que separa
al resto del código de la SDK de Anthropic. Antes de este módulo, cuatro
lugares distintos instanciaban `anthropic.Anthropic(...)` y llamaban
`client.messages.create(...)` directamente (vision_parser.py,
excel_parser.py, probar_manual.py, evals/runner.py) — cualquier cambio de
cómo se habla con el modelo (probar sin red, cambiar el forma de
autenticación, etc.) tocaba a los cuatro por separado.

Con este puerto, sólo `AdaptadorAnthropic.preguntar` conoce
`client.messages.create(...)`. Todo lo demás en el camino de extracción
(excel_parser, vision_parser, segunda_lectura, y quien las llame) habla
contra el Protocol `PuertoLLM`, que hoy tiene un solo método porque los
4+1 call sites reales de esta app sólo necesitan una cosa de la API:
mandar un system prompt + una lista de mensajes (texto plano o, para
vision, bloques de contenido con imagen/documento) y un tope de tokens, y
recibir el texto de la respuesta ya resuelto — nunca streaming en este
scope (eso lo hacen interpretacion.py y cruces_propuestos.py, fuera de
esta puerta a propósito).

`thinking` se declara explícito y en "disabled" por default acá mismo:
todos los call sites de hoy lo hacían así (ver claude_utils.extraer_texto,
que documenta por qué omitirlo es peligroso con `max_tokens` ajustado).
"""

from typing import Any, Optional, Protocol

from parser.vocabulario.claude_utils import extraer_texto

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


class PuertoLLM(Protocol):
    """Lo único que el camino de extracción necesita del LLM: mandar un
    prompt (system + messages) y recibir texto de vuelta. Los callers de
    este puerto no conocen `anthropic.Anthropic` ni `client.messages.create`
    — sólo este método."""

    def preguntar(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        thinking: Optional[dict] = None,
    ) -> str:
        ...


class AdaptadorAnthropic:
    """Único lugar del código (fuera de este módulo) que debe llamar
    `client.messages.create(...)` después de este refactor. Envuelve un
    `anthropic.Anthropic` real, o uno inyectado (tests: cualquier objeto
    con `.messages.create(**kwargs)` alcanza, no hace falta el SDK real)."""

    def __init__(self, client: Optional["anthropic.Anthropic"] = None, api_key: Optional[str] = None):
        if client is not None:
            self._client = client
        else:
            assert anthropic is not None, "Instalar el SDK: pip install anthropic --break-system-packages"
            self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def preguntar(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        thinking: Optional[dict] = None,
    ) -> str:
        respuesta = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            thinking=thinking if thinking is not None else {"type": "disabled"},
            system=system,
            messages=messages,
        )
        return extraer_texto(respuesta)
