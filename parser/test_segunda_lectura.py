"""
test_segunda_lectura.py

Sin pytest, sin API real (cliente mockeado con un objeto simple que imita
la forma de una respuesta de Anthropic): corre con
`python3 test_segunda_lectura.py`.
"""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from coverage import VariableValue
from segunda_lectura import (
    UMBRAL_CONFIANZA_BAJA,
    contrastar,
    pedir_segunda_lectura,
    pedir_segunda_lectura_imagen,
    variables_a_verificar,
)


def test_solo_selecciona_confianza_baja_no_reconciliada():
    variables = {
        "no_shows": VariableValue(57, "migracion_excel", 0.5),       # baja, sin reconciliar
        "turnos_agendados": VariableValue(73, "migracion_excel", 0.9),  # alta
        "monto_cobrado": VariableValue(100, "migracion_excel", 0.4),  # baja, pero ya reconciliada
    }
    resultado = variables_a_verificar(variables, variables_ya_reconciliadas={"monto_cobrado"})
    assert resultado == ["no_shows"]


def test_umbral_confianza_baja_es_07():
    assert UMBRAL_CONFIANZA_BAJA == 0.7


class _RespuestaFalsa:
    def __init__(self, payload: dict):
        self.content = [SimpleNamespace(type="text", text=json.dumps(payload))]
        self.stop_reason = "end_turn"


class _ClienteFalso:
    def __init__(self, payload: dict):
        self._payload = payload
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        return _RespuestaFalsa(self._payload)


def test_pedir_segunda_lectura_parsea_respuesta():
    payload = {"lecturas": [{"variable": "no_shows", "valor": 16, "confianza": 0.8, "nota": "conteo de filas ausentes"}]}
    cliente = _ClienteFalso(payload)
    lecturas = pedir_segunda_lectura(grid=[["mes", "no_shows"], ["Abril", 16]], variables=["no_shows"], client=cliente)
    assert lecturas["no_shows"]["valor"] == 16


def test_pedir_segunda_lectura_sin_variables_no_llama_api():
    cliente = _ClienteFalso({"lecturas": []})
    assert pedir_segunda_lectura(grid=[[1, 2]], variables=[], client=cliente) == {}


def test_contrastar_coincide_sube_confianza():
    variables = {"no_shows": VariableValue(16, "migracion_excel", 0.5)}
    lecturas = {"no_shows": {"valor": 16, "confianza": 0.8}}
    confianza_actualizada, discrepancias = contrastar(variables, lecturas)
    assert confianza_actualizada["no_shows"] == 0.7
    assert discrepancias == {}


def test_contrastar_no_coincide_genera_discrepancia():
    variables = {"no_shows": VariableValue(57, "migracion_excel", 0.5)}
    lecturas = {"no_shows": {"valor": 16, "confianza": 0.8, "nota": "conteo de filas ausentes"}}
    confianza_actualizada, discrepancias = contrastar(variables, lecturas)
    assert confianza_actualizada == {}
    assert discrepancias["no_shows"]["segunda_lectura"] == 16


# ---------------------------------------------------------------------------
# Bug #2 (E2E): una variable de origen migracion_foto no tiene grid de Excel
# para releer — pedir_segunda_lectura_imagen hace una relectura CIEGA de la
# imagen entera (sin contexto del primer mapeo) vía vision_parser.parsear_imagen
# y normaliza el resultado al mismo contrato {variable: {valor, confianza}}
# que ya devuelve pedir_segunda_lectura.
# ---------------------------------------------------------------------------

class _ClienteFalsoImagen:
    """Mismo patrón que test_vision_parser.py: cliente falso que responde
    con `payload` sin llamar a la API real, capturando la llamada."""

    def __init__(self, payload: dict):
        self._payload = payload
        self.ultima_llamada = None
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.ultima_llamada = kwargs
        return _RespuestaFalsa(self._payload)


def _archivo_temporal_imagen():
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    f.write(b"contenido-falso-no-es-una-imagen-real")
    f.close()
    return f.name


def test_pedir_segunda_lectura_imagen_normaliza_al_contrato_de_lectura():
    path = _archivo_temporal_imagen()
    payload = {"variables_encontradas": [
        {"variable": "no_shows", "valor": 16, "confianza": 0.8, "etiqueta_fila": "No-shows", "nota": "..."},
    ]}
    cliente = _ClienteFalsoImagen(payload)
    lecturas = pedir_segunda_lectura_imagen(path, ["no_shows"], cliente)
    assert lecturas["no_shows"]["valor"] == 16
    assert lecturas["no_shows"]["confianza"] == 0.8
    Path(path).unlink()


def test_pedir_segunda_lectura_imagen_sin_variables_no_llama_api():
    path = _archivo_temporal_imagen()
    cliente = _ClienteFalsoImagen({"variables_encontradas": []})
    assert pedir_segunda_lectura_imagen(path, [], cliente) == {}
    assert cliente.ultima_llamada is None, "sin variables no debe invocar a la API"
    Path(path).unlink()


def test_pedir_segunda_lectura_imagen_descarta_variables_no_pedidas():
    # La relectura de la imagen entera puede volver a encontrar variables
    # que no eran las dudosas — solo se normalizan las pedidas, el resto se
    # descarta (mismo criterio que pedir_segunda_lectura con `definiciones`).
    path = _archivo_temporal_imagen()
    payload = {"variables_encontradas": [
        {"variable": "no_shows", "valor": 16, "confianza": 0.8},
        {"variable": "turnos_agendados", "valor": 40, "confianza": 0.9},
    ]}
    cliente = _ClienteFalsoImagen(payload)
    lecturas = pedir_segunda_lectura_imagen(path, ["no_shows"], cliente)
    assert list(lecturas.keys()) == ["no_shows"]
    Path(path).unlink()


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
