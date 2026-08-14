"""
puerto_llm.py

Puerto (Strategy/Adapter, scope: solo el camino de extracción) que separa
al resto del código de la SDK de Anthropic. Antes de este módulo, cuatro
lugares distintos instanciaban `anthropic.Anthropic(...)` y llamaban
`client.messages.create(...)` directamente (vision_parser.py,
excel_parser.py, probar_manual.py, evals/runner.py) — cualquier cambio de
cómo se habla con el modelo (probar sin red, cambiar el forma de
autenticación, etc.) tocaba a los cuatro por separado.

Con este puerto, sólo `AdaptadorAnthropic` conoce
`client.messages.create(...)`. Todo lo demás en el camino de extracción
(excel_parser, vision_parser, segunda_lectura, y quien las llame) habla
contra el Protocol `PuertoLLM.preguntar`, porque los 4+1 call sites reales
de esta app sólo necesitan una cosa de la API: mandar un system prompt +
una lista de mensajes (texto plano o, para vision, bloques de contenido
con imagen/documento) y un tope de tokens, y recibir el texto de la
respuesta ya resuelto — nunca streaming en este scope (eso lo sigue
haciendo `interpretar_clinica` en interpretacion.py, fuera de esta puerta
a propósito).

`deuda-panel-sistemas-puertollm` (U1) sumó `preguntar_con_truncamiento`,
que además devuelve si la respuesta se cortó por `max_tokens` — lo usan
`interpretar_kpi`/`interpretar_panel` (interpretacion.py) y
`proponer_cruces` (cruces_propuestos.py), que antes hablaban contra el
cliente crudo de Anthropic y necesitaban esa señal para no presentar un
texto cortado como si fuera una respuesta completa.

`thinking` se declara explícito y en "disabled" por default acá mismo:
todos los call sites de hoy lo hacían así (ver claude_utils.extraer_texto,
que documenta por qué omitirlo es peligroso con `max_tokens` ajustado).
"""

from typing import Any, Optional, Protocol

from parser.vocabulario.claude_utils import extraer_texto, respuesta_truncada

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

    def preguntar_con_truncamiento(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        thinking: Optional[dict] = None,
    ) -> tuple[str, bool]:
        """Igual que `preguntar`, pero además devuelve si la respuesta se
        cortó por `max_tokens` (`respuesta_truncada`) en vez de terminar
        sola. Método aparte (no un cambio de firma sobre `preguntar`)
        porque los 4+1 call sites de extracción que ya usan `preguntar()`
        no necesitan ni quieren esa segunda pieza de información — sólo
        `interpretar_kpi`/`interpretar_panel`/`proponer_cruces`
        (deuda-panel-sistemas-puertollm, U1), que antes leían
        `respuesta_truncada(respuesta)` directo sobre el objeto crudo del
        SDK y perderían esa señal si se migraran a un `preguntar()` que
        sólo devuelve `str`."""
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

    def preguntar_con_truncamiento(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        thinking: Optional[dict] = None,
    ) -> tuple[str, bool]:
        respuesta = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            thinking=thinking if thinking is not None else {"type": "disabled"},
            system=system,
            messages=messages,
        )
        return extraer_texto(respuesta), respuesta_truncada(respuesta)
