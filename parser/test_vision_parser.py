"""
test_vision_parser.py

Sin pytest, sin API real (mismo patrón de cliente mockeado que
test_segunda_lectura.py): corre con `python3 test_vision_parser.py`.

vision_parser.py no tenía ningún test hasta la Fase H3 — nunca se había
corrido ni siquiera headless.
"""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from schema import VARIABLE_TYPES
from extractors.vision_parser import SYSTEM_PROMPT, _VARIABLES_FOTO, _media_type, parsear_imagen


class _RespuestaFalsa:
    def __init__(self, payload: dict):
        self.content = [SimpleNamespace(type="text", text=json.dumps(payload))]
        self.stop_reason = "end_turn"


class _ClienteFalso:
    def __init__(self, payload: dict):
        self._payload = payload
        self.ultima_llamada = None
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.ultima_llamada = kwargs
        return _RespuestaFalsa(self._payload)


def _archivo_temporal(sufijo=".jpg"):
    f = tempfile.NamedTemporaryFile(delete=False, suffix=sufijo)
    f.write(b"contenido-falso-no-es-una-imagen-real")
    f.close()
    return f.name


def test_fuente_queda_en_migracion_foto():
    path = _archivo_temporal()
    payload = {"variables_encontradas": [{"variable": "no_shows", "valor": 16, "confianza": 0.7}]}
    cliente = _ClienteFalso(payload)
    variables = parsear_imagen(path, client=cliente)
    assert variables["no_shows"].fuente == "migracion_foto"
    Path(path).unlink()


def test_variable_fuera_del_vocabulario_se_descarta():
    path = _archivo_temporal()
    payload = {"variables_encontradas": [{"variable": "inventada_por_el_modelo", "valor": 1, "confianza": 0.5}]}
    cliente = _ClienteFalso(payload)
    variables = parsear_imagen(path, client=cliente)
    assert variables == {}
    Path(path).unlink()


def test_item_sin_valor_no_tira_abajo_el_lote():
    path = _archivo_temporal()
    payload = {"variables_encontradas": [
        {"variable": "no_shows"},  # falta "valor" — mal formado
        {"variable": "resenas_nuevas", "valor": 9, "confianza": 0.8},
    ]}
    cliente = _ClienteFalso(payload)
    variables = parsear_imagen(path, client=cliente)
    assert "no_shows" not in variables
    assert variables["resenas_nuevas"].valor == 9
    Path(path).unlink()


def test_item_sin_variable_no_tira_abajo_el_lote():
    path = _archivo_temporal()
    payload = {"variables_encontradas": [
        {"valor": 5, "confianza": 0.5},  # falta "variable"
        {"variable": "pacientes_reactivados", "valor": 12, "confianza": 0.6},
    ]}
    cliente = _ClienteFalso(payload)
    variables = parsear_imagen(path, client=cliente)
    assert len(variables) == 1
    assert variables["pacientes_reactivados"].valor == 12
    Path(path).unlink()


def test_confianza_por_defecto_es_06():
    path = _archivo_temporal()
    payload = {"variables_encontradas": [{"variable": "no_shows", "valor": 16}]}
    cliente = _ClienteFalso(payload)
    variables = parsear_imagen(path, client=cliente)
    assert variables["no_shows"].confianza == 0.6
    Path(path).unlink()


def test_thinking_disabled_declarado():
    path = _archivo_temporal()
    payload = {"variables_encontradas": []}
    cliente = _ClienteFalso(payload)
    parsear_imagen(path, client=cliente)
    assert cliente.ultima_llamada["thinking"] == {"type": "disabled"}
    Path(path).unlink()


def test_variable_tipo_ledger_nunca_se_mapea_desde_una_foto():
    path = _archivo_temporal()
    payload = {"variables_encontradas": [{"variable": "ledger_pacientes", "valor": 1240, "confianza": 0.85}]}
    cliente = _ClienteFalso(payload)
    variables = parsear_imagen(path, client=cliente)
    assert variables == {}
    Path(path).unlink()


def test_system_prompt_ancla_cada_valor_a_la_etiqueta_de_su_propia_fila():
    # Bug #1a (E2E): una foto con corrimiento vertical uniforme — cada
    # valor leído un renglón más abajo que su etiqueta real — pasaba con
    # confianza alta porque el prompt nunca pedía verificar que el valor
    # perteneciera a LA MISMA fila que su etiqueta. Ahora el modelo debe
    # devolver, por cada valor, la etiqueta que está en su misma fila
    # ("etiqueta_fila") y bajar la confianza si hay duda de la alineación.
    assert "misma fila" in SYSTEM_PROMPT
    assert "etiqueta_fila" in SYSTEM_PROMPT


def test_system_prompt_pide_confianza_baja_ante_duda_de_alineacion_de_fila():
    # Segunda mitad del requisito #1a: no alcanza con pedir la etiqueta,
    # también hay que bajar la confianza cuando la pareja valor-etiqueta es
    # dudosa (mismo criterio que ya existía para dígitos manuscritos
    # ambiguos, extendido a la alineación de filas).
    assert "duda" in SYSTEM_PROMPT and "fila" in SYSTEM_PROMPT


def test_variables_foto_sigue_derivado_del_schema_sin_hardcodear():
    # El endurecimiento del prompt (#1a) no debe tocar el vocabulario: sigue
    # siendo VARIABLE_TYPES menos "list"/"ledger", nunca una lista copiada
    # a mano en el prompt.
    assert "ledger_pacientes" not in _VARIABLES_FOTO
    assert set(_VARIABLES_FOTO) == {
        v for v in VARIABLE_TYPES if VARIABLE_TYPES[v] not in ("list", "ledger")
    }


def test_media_type_resuelve_extensiones_conocidas():
    assert _media_type("foto.png") == "image/png"
    assert _media_type("foto.jpg") == "image/jpeg"
    assert _media_type("foto.jpeg") == "image/jpeg"
    assert _media_type("foto.webp") == "image/webp"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
