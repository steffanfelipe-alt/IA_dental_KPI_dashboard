"""
test_estrategias.py

Sin pytest: corre con `python -m parser.extraccion.test_estrategias`.

Cubre que cada EstrategiaExtraccion (Excel, imagen, PDF) devuelva siempre
un ResultadoExtraccion bien formado a partir de un PuertoLLM falso — sin
llamar a la API real ni instanciar anthropic.Anthropic.
"""

import json
import tempfile
from pathlib import Path

from parser.extraccion.estrategias import (
    ExtraccionExcel, ExtraccionVisionImagen, ExtraccionVisionPDF, ResultadoExtraccion,
)


class _PuertoLLMFalso:
    """Fake de PuertoLLM: .preguntar(...) devuelve directamente el texto
    (JSON serializado) que el llamador espera, sin pasar por
    anthropic.Anthropic — mismo espíritu que los _ClienteFalso de los
    tests viejos, pero ya en la forma que expone el puerto (un método,
    no .messages.create)."""

    def __init__(self, payload: dict):
        self._texto = json.dumps(payload)
        self.ultima_llamada = None

    def preguntar(self, **kwargs) -> str:
        self.ultima_llamada = kwargs
        return self._texto


def _csv_temporal(contenido: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", newline="")
    f.write(contenido)
    f.close()
    return f.name


def _archivo_temporal(sufijo: str) -> str:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=sufijo)
    f.write(b"contenido-falso-no-es-un-archivo-real")
    f.close()
    return f.name


def test_extraccion_excel_devuelve_resultado_extraccion_con_tasas():
    path = _csv_temporal("mes,ausencias\nAbril 2026,16\n")
    payload = {"hojas": [{
        "hoja": None, "fila_encabezado": 0, "orientacion": "periodos_en_filas", "columna_periodo": 0,
        "mapeo": [{"columna_index": 1, "variable": "no_shows", "agregacion": "sum", "confianza": 0.9}],
    }]}
    resultado = ExtraccionExcel().extraer(path, _PuertoLLMFalso(payload))
    assert isinstance(resultado, ResultadoExtraccion)
    assert resultado.variables["no_shows"].valor == 16.0
    assert resultado.tasas_declaradas == {}
    Path(path).unlink()


def test_extraccion_excel_acepta_registro_clientes_y_lo_usa():
    # El mismo caso real de test_excel_parser.py, pero pasando por la
    # capa de Strategy: la variante que hoy resuelve matching.py sigue
    # resolviendo cuando se llega vía ExtraccionExcel.extraer.
    from parser.pacientes.matching import RegistroClientes

    path = _csv_temporal("paciente,monto\nJuan Perez,50000\nJ. Perez,30000\n")
    payload = {"hojas": [{
        "hoja": None, "fila_encabezado": 0, "orientacion": "transaccional",
        "mapeo": [{"columna_index": 1, "variable": "ingreso_por_paciente", "agregacion": "sum",
                   "columna_categoria_index": 0, "confianza": 0.9}],
    }]}
    resultado = ExtraccionExcel().extraer(path, _PuertoLLMFalso(payload), registro_clientes=RegistroClientes())
    assert len(resultado.variables["ingreso_por_paciente"].valor) == 1, (
        "Juan Perez y J. Perez deberían resolver al mismo paciente"
    )
    Path(path).unlink()


def test_extraccion_vision_imagen_devuelve_resultado_extraccion_sin_tasas():
    path = _archivo_temporal(".jpg")
    payload = {"variables_encontradas": [{"variable": "no_shows", "valor": 16, "confianza": 0.7}]}
    resultado = ExtraccionVisionImagen().extraer(path, _PuertoLLMFalso(payload))
    assert isinstance(resultado, ResultadoExtraccion)
    assert resultado.variables["no_shows"].valor == 16
    assert resultado.tasas_declaradas == {}, "vision_parser nunca conoce tasas_declaradas"
    Path(path).unlink()


def test_extraccion_vision_imagen_ignora_registro_clientes_sin_romper():
    # El contrato EstrategiaExtraccion exige aceptar el parámetro aunque
    # no lo use — nunca debe tirar TypeError por recibirlo.
    from parser.pacientes.matching import RegistroClientes

    path = _archivo_temporal(".jpg")
    payload = {"variables_encontradas": []}
    resultado = ExtraccionVisionImagen().extraer(
        path, _PuertoLLMFalso(payload), registro_clientes=RegistroClientes(),
    )
    assert resultado.variables == {}
    Path(path).unlink()


def test_extraccion_vision_pdf_devuelve_resultado_extraccion():
    path = _archivo_temporal(".pdf")
    payload = {"variables_encontradas": [{"variable": "turnos_agendados", "valor": 40, "confianza": 0.6}]}
    resultado = ExtraccionVisionPDF().extraer(path, _PuertoLLMFalso(payload))
    assert isinstance(resultado, ResultadoExtraccion)
    assert resultado.variables["turnos_agendados"].valor == 40
    assert resultado.tasas_declaradas == {}
    Path(path).unlink()


def test_resultado_extraccion_tasas_declaradas_default_vacio():
    # El dataclass tiene que dar {} por default, no None ni un mutable
    # compartido entre instancias (default_factory, no default=[]).
    a = ResultadoExtraccion(variables={})
    b = ResultadoExtraccion(variables={})
    a.tasas_declaradas[1] = "x"
    assert b.tasas_declaradas == {}, "el default no puede compartirse entre instancias"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
