"""
test_claude_utils.py

Sin pytest: corre con `python3 test_claude_utils.py`.

Cubre extraer_json — bug real: vision_parser.parsear_imagen rompía con
JSONDecodeError: Expecting value: line 1 column 1 (char 0) al procesar
una foto ambigua, porque el parseo viejo (`texto.split("```")[1]`) exigía
que el string ENTERO fuera un fence, sin tolerar una frase antes del
bloque, un fence sin cerrar, o ausencia total de fence.
"""

from claude_utils import extraer_json


class _Bloque:
    def __init__(self, tipo, texto=""):
        self.type, self.text = tipo, texto


class _Respuesta:
    def __init__(self, content, stop_reason="end_turn"):
        self.content, self.stop_reason = content, stop_reason


def test_json_en_fence_bien_cerrado_parsea_igual_que_antes():
    texto = '```json\n{"variables_encontradas": [], "descripcion_imagen": "ok"}\n```'
    respuesta = _Respuesta([_Bloque("text", texto)])
    payload = extraer_json(respuesta)
    assert payload == {"variables_encontradas": [], "descripcion_imagen": "ok"}


def test_frase_antes_del_fence_ya_no_rompe_el_parseo():
    """El caso real que rompió: Claude antepone una aclaración antes del
    bloque ```json cuando la imagen es ambigua (letra manuscrita)."""
    texto = (
        "No puedo leer con certeza un par de valores manuscritos, pero "
        "esta es mi mejor lectura:\n\n"
        '```json\n{"variables_encontradas": [{"variable": "no_shows", '
        '"valor": 5, "confianza": 0.4, "nota": "manuscrito"}], '
        '"descripcion_imagen": "foto de planilla"}\n```'
    )
    respuesta = _Respuesta([_Bloque("text", texto)])
    payload = extraer_json(respuesta)
    assert payload["descripcion_imagen"] == "foto de planilla"
    assert payload["variables_encontradas"][0]["variable"] == "no_shows"


def test_fence_sin_cerrar_igual_parsea():
    texto = '```json\n{"variables_encontradas": [], "descripcion_imagen": "sin cierre"}'
    respuesta = _Respuesta([_Bloque("text", texto)])
    payload = extraer_json(respuesta)
    assert payload["descripcion_imagen"] == "sin cierre"


def test_json_sin_ningun_fence_parsea_igual():
    texto = '{"variables_encontradas": [], "descripcion_imagen": "sin fence"}'
    respuesta = _Respuesta([_Bloque("text", texto)])
    payload = extraer_json(respuesta)
    assert payload["descripcion_imagen"] == "sin fence"


def test_prosa_sin_json_levanta_valueerror_con_el_texto_crudo():
    texto = "Lo siento, no puedo determinar ningún dato en esta imagen."
    respuesta = _Respuesta([_Bloque("text", texto)])
    try:
        extraer_json(respuesta)
    except ValueError as e:
        assert "Lo siento" in str(e), "el error debe incluir el texto crudo, no quedar mudo"
    else:
        raise AssertionError("debía fallar: no hay JSON en la respuesta")


def test_texto_vacio_levanta_valueerror_claro_no_json_pelado():
    respuesta = _Respuesta([_Bloque("text", "")])
    try:
        extraer_json(respuesta)
    except ValueError as e:
        assert "No encontré un objeto JSON" in str(e)
    else:
        raise AssertionError("debía fallar: texto vacío no tiene JSON")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
