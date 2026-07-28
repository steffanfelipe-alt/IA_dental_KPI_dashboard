"""
test_evals_diagnostico.py

Sin pytest: corre con `python3 test_evals_diagnostico.py`.
Envoltorio de evals/runner_diagnostico.py como test de regresión: a
diferencia de evals/runner.py (que llama a la API real), este es 100%
determinista (diagnostico.py no usa Claude), así que tiene sentido que
corra en la misma suite que el resto — cualquier cambio en
diagnostico.py/catalogo_tecnologico.py/priorizacion.py que rompa un caso
sintético se detecta acá, no solo corriendo el runner a mano.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "evals"))

import casos_diagnostico as datos  # noqa: E402
from runner_diagnostico import _correr_caso, _evaluar_caso  # noqa: E402


def test_todos_los_casos_sinteticos_pasan_sus_propios_checks():
    fallas = []
    for caso in datos.CASOS:
        resultado = _correr_caso(caso)
        for nombre, ok, detalle in _evaluar_caso(caso, resultado):
            if not ok:
                fallas.append(f"{caso.nombre}.{nombre}: {detalle}")
    assert not fallas, "checks fallidos:\n" + "\n".join(fallas)


def test_ningun_caso_sano_genera_falso_diagnostico():
    for caso in datos.CASOS:
        if not caso.debe_generar_oportunidades:
            resultado = _correr_caso(caso)
            assert resultado["oportunidades"] == [], f"{caso.nombre} no debería generar oportunidades"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
