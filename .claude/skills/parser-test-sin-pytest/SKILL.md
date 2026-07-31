---
name: parser-test-sin-pytest
description: Escribir un test_*.py nuevo o sumar tests a uno existente siguiendo la convención EXACTA del repo — sin pytest, runner standalone, naming largo en español. Usar siempre que se agregue cobertura de tests a parser/. NO introducir pytest.
---

# Escribir un test sin pytest

La suite son 26 archivos `test_*.py`, uno por módulo, 363 tests, **sin pytest**. Cada archivo
corre standalone. Introducir pytest o un fixture de pytest rompe la convención — no hacerlo.

## Estructura exacta de un archivo

```python
"""
test_<modulo>.py

Sin pytest: corre con `python3 test_<modulo>.py`.
Cubre <qué fase/hallazgo> — <una línea de por qué existe>.
[Decir si llama a la API real o no. La regla es: NO, se inyecta un cliente falso.]
"""

from <modulo> import <lo_que_se_prueba>


def test_nombre_largo_y_descriptivo_en_espanol_que_dice_el_caso():
    # Comentario que explica el BUG/HALLAZGO que motiva el assert, no el qué.
    resultado = funcion(...)
    assert resultado == esperado, "mensaje con el valor real si falla"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
```

## Convenciones

- **Naming largo en español**, que describe el caso completo:
  `test_juan_y_juana_no_se_fusionan_solos_aunque_el_score_bruto_sea_alto`,
  `test_ids_estables_no_se_fusionan_por_matching_difuso`. No `test_1`, no `test_matching`.
- **Un comentario por assert** explicando el bug real que fija (trampa tasa-vs-conteo, fila
  TOTAL/Prom. promediada, etc.) — es la práctica del repo.
- **Tests deterministas, sin red.** Dos formas de evitar la API:
  - `client=None` — los entry points que lo aceptan devuelven el payload crudo sin llamar
    (`test_interpretacion.py`).
  - **Cliente falso** cuando querés inspeccionar la llamada: `_ClienteFalso` /
    `SimpleNamespace(create=lambda **kw: _RespuestaFalsa(...))` que captura `ultima_llamada`
    (`test_vision_parser.py`). Reemplazar `pipeline.EXTRACTOR_POR_EXTENSION` por extractores
    falsos y restaurarlo en un `finally` (`test_pipeline.py`).
- **Helpers cortos** por archivo: `_vv`, `_tasas`, `_archivo_temporal` — reusar el estilo del
  módulo que estás testeando.

## Correr

```
python3 test_<modulo>.py
```

Imprime `OK  <nombre>` por test y el total. Verde = todos pasaron. Reportar el conteo nuevo si
actualizás el README (la métrica trackeada es el total de tests verdes).

## Para evals (aparte de los tests)

`evals/` SÍ llama a la API real (`runner.py`) y compara contra valores dorados con tolerancia
porcentual (`_cerca`, 0.5%). Si agregás un caso dorado, mantené la fuente única de verdad:
`generar_fixtures.py` y `casos_dorados.py` derivan de los mismos arrays, no los desincronices.
`runner_diagnostico.py` es determinista y ya entra a la suite vía `test_evals_diagnostico.py`.
