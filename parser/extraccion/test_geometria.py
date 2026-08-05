"""
test_geometria.py

Sin pytest: corre con `python -m parser.extraccion.test_geometria`.

Cubre `contrastar_filas` (agreement sube confianza, corrimiento de fila
genera discrepancia) y el fail-closed de `AdaptadorGeometriaVendor` sin
`GEOMETRIA_API_KEY` — sin llamar a ningún vendor real ni instanciar su SDK.
"""

import os

from parser.cobertura_calidad.coverage import VariableValue
from parser.extraccion.geometria import contrastar_filas
from parser.vocabulario.puerto_geometria import AdaptadorGeometriaVendor, FilaGeometrica


class _PuertoGeometriaFalso:
    """Fake de PuertoGeometria: .ordenar_filas(path) devuelve directamente
    la lista de FilaGeometrica preseteada, sin llamar a ningún vendor real
    — mismo espíritu que _PuertoLLMFalso en test_estrategias.py."""

    def __init__(self, filas: list[FilaGeometrica]):
        self._filas = filas
        self.ultimo_path = None

    def ordenar_filas(self, path: str) -> list[FilaGeometrica]:
        self.ultimo_path = path
        return self._filas


def _variable_con_etiqueta(valor, confianza, etiqueta_fila):
    vv = VariableValue(valor, "migracion_foto", confianza)
    vv.etiqueta_fila = etiqueta_fila  # Fase 2 agrega este campo de forma real
    return vv


def test_puerto_geometria_falso_registra_el_path_y_no_llama_red():
    filas = [FilaGeometrica(etiqueta="No-shows", y_top=0.1, orden=0)]
    puerto = _PuertoGeometriaFalso(filas)
    resultado = puerto.ordenar_filas("/tmp/foto.jpg")
    assert resultado == filas
    assert puerto.ultimo_path == "/tmp/foto.jpg"


def test_contrastar_filas_coincide_sube_confianza():
    variables = {
        "no_shows": _variable_con_etiqueta(16, 0.5, "No-shows"),
    }
    filas_geometricas = [FilaGeometrica(etiqueta="No-shows", y_top=0.1, orden=0)]
    confianza_actualizada, discrepancias = contrastar_filas(variables, filas_geometricas)
    assert confianza_actualizada["no_shows"] == 0.7
    assert discrepancias == {}


def test_contrastar_filas_corrimiento_de_fila_no_sube_confianza_y_genera_discrepancia():
    # "no_shows" es la primera variable con etiqueta_fila (orden original 0),
    # pero la geometría la detecta en la fila 2 — un corrimiento de 2,
    # mayor que la tolerancia default (1).
    variables = {
        "no_shows": _variable_con_etiqueta(16, 0.5, "No-shows"),
    }
    filas_geometricas = [
        FilaGeometrica(etiqueta="Turnos agendados", y_top=0.05, orden=0),
        FilaGeometrica(etiqueta="Cancelaciones", y_top=0.15, orden=1),
        FilaGeometrica(etiqueta="No-shows", y_top=0.25, orden=2),
    ]
    confianza_actualizada, discrepancias = contrastar_filas(variables, filas_geometricas)
    assert confianza_actualizada == {}
    assert discrepancias["no_shows"] == {
        "etiqueta": "No-shows",
        "original_orden": 0,
        "orden_geometria": 2,
    }


def test_contrastar_filas_devuelve_mismo_shape_de_tupla_que_contrastar():
    confianza_actualizada, discrepancias = contrastar_filas({}, [])
    assert isinstance(confianza_actualizada, dict)
    assert isinstance(discrepancias, dict)


def test_contrastar_filas_variable_sin_etiqueta_fila_se_salta_en_silencio():
    # Hoy (antes de la Fase 2) ninguna VariableValue real tiene
    # etiqueta_fila — contrastar_filas no debe romper, solo no contrastar
    # nada para esa variable.
    variables = {"no_shows": VariableValue(16, "migracion_foto", 0.5)}
    filas_geometricas = [FilaGeometrica(etiqueta="No-shows", y_top=0.1, orden=0)]
    confianza_actualizada, discrepancias = contrastar_filas(variables, filas_geometricas)
    assert confianza_actualizada == {}
    assert discrepancias == {}


def test_adaptador_geometria_vendor_sin_api_key_falla_cerrado():
    valor_previo = os.environ.pop("GEOMETRIA_API_KEY", None)
    try:
        fallo = False
        try:
            AdaptadorGeometriaVendor()
        except RuntimeError as error:
            fallo = True
            assert "GEOMETRIA_API_KEY" in str(error)
        assert fallo, "sin GEOMETRIA_API_KEY tiene que fallar cerrado, no intentar mandar nada"
    finally:
        if valor_previo is not None:
            os.environ["GEOMETRIA_API_KEY"] = valor_previo


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
