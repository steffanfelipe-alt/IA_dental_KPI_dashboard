"""
test_puerto_llm.py

Sin pytest: corre con `python -m parser.vocabulario.test_puerto_llm`.

AdaptadorAnthropic es el único lugar del código (fuera de este módulo)
que después de la Fase Strategy+Adapter puede llamar
`client.messages.create(...)` — este test cubre que arma esa llamada bien
(model/system/messages/max_tokens/thinking) y que devuelve el texto ya
extraído (reusa claude_utils.extraer_texto, mismo criterio que usaba cada
extractor antes de que existiera el puerto).
"""

from types import SimpleNamespace

from parser.vocabulario.puerto_llm import AdaptadorAnthropic


class _RespuestaFalsa:
    def __init__(self, texto: str, stop_reason="end_turn"):
        self.content = [SimpleNamespace(type="text", text=texto)]
        self.stop_reason = stop_reason


class _ClienteFalso:
    """Imita anthropic.Anthropic: sólo expone .messages.create y captura
    los kwargs de la última llamada, sin pegarle nunca a la red."""

    def __init__(self, texto_respuesta: str):
        self._texto_respuesta = texto_respuesta
        self.ultima_llamada = None
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.ultima_llamada = kwargs
        return _RespuestaFalsa(self._texto_respuesta)


def test_preguntar_devuelve_el_texto_de_la_respuesta():
    cliente = _ClienteFalso('{"ok": true}')
    adaptador = AdaptadorAnthropic(cliente)
    texto = adaptador.preguntar(
        model="claude-sonnet-5", system="sos un test", max_tokens=100,
        messages=[{"role": "user", "content": "hola"}],
    )
    assert texto == '{"ok": true}'


def test_preguntar_pasa_model_system_messages_y_max_tokens_al_cliente():
    # El adaptador no puede perder ni renombrar ningún argumento en el
    # camino: es lo único que separa "habla con Claude" de "no habla con
    # nadie" para los 4+1 call sites reales de esta app.
    cliente = _ClienteFalso("listo")
    adaptador = AdaptadorAnthropic(cliente)
    adaptador.preguntar(
        model="claude-sonnet-5", system="sistema", max_tokens=42,
        messages=[{"role": "user", "content": "hola"}],
    )
    assert cliente.ultima_llamada["model"] == "claude-sonnet-5"
    assert cliente.ultima_llamada["system"] == "sistema"
    assert cliente.ultima_llamada["max_tokens"] == 42
    assert cliente.ultima_llamada["messages"] == [{"role": "user", "content": "hola"}]


def test_thinking_disabled_por_defecto_si_no_se_declara():
    # Los 4+1 call sites de hoy siempre pasaban thinking={"type": "disabled"}
    # explícito — el adaptador no debe inventar otro default si algún
    # llamador futuro lo omite (mismo comportamiento de siempre, ver
    # claude_utils.extraer_texto sobre el peligro de omitirlo con
    # max_tokens ajustado).
    cliente = _ClienteFalso("listo")
    adaptador = AdaptadorAnthropic(cliente)
    adaptador.preguntar(model="m", system="s", max_tokens=10, messages=[])
    assert cliente.ultima_llamada["thinking"] == {"type": "disabled"}


def test_thinking_explicito_se_respeta():
    cliente = _ClienteFalso("listo")
    adaptador = AdaptadorAnthropic(cliente)
    adaptador.preguntar(
        model="m", system="s", max_tokens=10, messages=[],
        thinking={"type": "enabled", "budget_tokens": 1024},
    )
    assert cliente.ultima_llamada["thinking"] == {"type": "enabled", "budget_tokens": 1024}


def test_preguntar_usa_extraer_texto_y_saltea_bloques_de_thinking():
    # Con thinking activado, la respuesta puede traer un ThinkingBlock antes
    # del bloque de texto real — el adaptador debe reusar la lógica de
    # claude_utils.extraer_texto en vez de asumir content[0].
    class _RespuestaConThinking:
        def __init__(self):
            self.content = [
                SimpleNamespace(type="thinking", text="pensando..."),
                SimpleNamespace(type="text", text="resultado final"),
            ]
            self.stop_reason = "end_turn"

    class _ClienteConThinking:
        def __init__(self):
            self.messages = SimpleNamespace(create=lambda **kwargs: _RespuestaConThinking())

    adaptador = AdaptadorAnthropic(_ClienteConThinking())
    texto = adaptador.preguntar(model="m", system="s", max_tokens=10, messages=[])
    assert texto == "resultado final"


# ---------------------------------------------------------------------------
# deuda-panel-sistemas-puertollm (U1): preguntar_con_truncamiento — mismo
# preguntar() de arriba, pero además devuelve si la respuesta se cortó por
# max_tokens. `preguntar()` en sí queda intacta (ver tests de arriba).
# ---------------------------------------------------------------------------

def test_preguntar_con_truncamiento_devuelve_texto_y_false_en_respuesta_completa():
    cliente = _ClienteFalso("informe completo")
    adaptador = AdaptadorAnthropic(cliente)
    texto, truncado = adaptador.preguntar_con_truncamiento(
        model="m", system="s", max_tokens=10, messages=[],
    )
    assert texto == "informe completo"
    assert truncado is False


def test_preguntar_con_truncamiento_marca_true_cuando_stop_reason_es_max_tokens():
    class _ClienteTruncado:
        def __init__(self):
            self.messages = SimpleNamespace(
                create=lambda **kwargs: _RespuestaFalsa("texto cortado a la mit", stop_reason="max_tokens"),
            )

    adaptador = AdaptadorAnthropic(_ClienteTruncado())
    texto, truncado = adaptador.preguntar_con_truncamiento(
        model="m", system="s", max_tokens=10, messages=[],
    )
    assert texto == "texto cortado a la mit"
    assert truncado is True


def test_adaptador_acepta_un_cliente_inyectado_sin_necesitar_el_sdk_real():
    # Nunca debe intentar `anthropic.Anthropic()` cuando se le pasa un
    # cliente — así los tests (y evals/runner.py, probar_manual.py) pueden
    # construirlo con un client ya armado sin tocar variables de entorno.
    cliente = _ClienteFalso("ok")
    adaptador = AdaptadorAnthropic(cliente)
    assert adaptador._client is cliente


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
