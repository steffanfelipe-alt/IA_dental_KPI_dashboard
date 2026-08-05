"""
geometria.py

Verificación de geometría para filas de fotos (Bug #1a): un "arquero"
independiente y determinístico — sin LLM — que contrasta el orden de
filas que un vendor de Document AI detecta geométricamente contra el
orden que Claude reportó por su cuenta (`etiqueta_fila` en cada
`VariableValue`, ver vision_parser.py).

Mismo rol estructural que segunda_lectura.contrastar(): NO reemplaza la
extracción semántica de Claude, solo la audita desde otro ángulo (acá,
layout real vs. layout auto-reportado) y alimenta la MISMA maquinaria de
confianza/conflicto — por eso `contrastar_filas` devuelve exactamente la
misma forma de tupla que `segunda_lectura.contrastar`:
(confianza_actualizada, discrepancias).

De dónde sale el "orden original"
----------------------------------
`VariableValue` (Fase 2 de este cambio) va a tener `etiqueta_fila`, pero
ningún campo de índice/orden — Claude no reporta "esta es la fila 3", solo
el texto de la fila. El "orden original" que se contrasta acá es, por
eso, la POSICIÓN de cada variable dentro de `variables` (un dict, que en
Python 3.7+ preserva orden de inserción): vision_parser.parsear_imagen
arma ese dict recorriendo "variables_encontradas" en el mismo orden en que
Claude las devolvió, que a su vez sigue el orden de lectura de la imagen
— así que ese orden de inserción ES el orden que Claude implícitamente le
asignó a cada fila, sin que haga falta agregarle un campo aparte a
VariableValue solo para esto.

Se lee `etiqueta_fila` con `getattr(..., None)` en vez de acceso directo:
esta Fase (1) no toca `VariableValue` (eso es la Fase 2 de este cambio),
así que hoy ese atributo puede no existir todavía en instancias reales —
`None` es el "no hay con qué contrastar, se salta en silencio" ya usado
en el resto del código para campos opcionales.
"""

from parser.cobertura_calidad.coverage import VariableValue
from parser.vocabulario.puerto_geometria import FilaGeometrica

# Cuántas posiciones de diferencia entre el orden que Claude implicó y el
# orden geométrico real se toleran antes de considerarlo un desacuerdo.
# Valor inicial arbitrario (1 = permite un corrimiento de una sola fila,
# p. ej. un encabezado que Claude sí contó y la geometría no, o viceversa)
# — ver Open Question en design.md: hace falta ajustarlo contra fotos
# reales una vez que haya un vendor elegido (Fase 5), no se lo trata como
# definitivo acá.
TOLERANCIA_ORDEN_DEFAULT = 1


def contrastar_filas(
    variables: dict[str, VariableValue],
    filas_geometricas: list[FilaGeometrica],
    tolerancia_orden: int = TOLERANCIA_ORDEN_DEFAULT,
) -> tuple[dict[str, float], dict[str, dict]]:
    """
    Compara, para cada variable con `etiqueta_fila` seteado, su orden
    original (posición dentro de `variables`, ver docstring del módulo)
    contra el orden que la geometría detectó para esa misma etiqueta.
    Devuelve (confianza_actualizada, discrepancias) — mismo contrato que
    segunda_lectura.contrastar: no decide sola qué valor usar cuando hay
    desacuerdo, eso lo resuelve el mecanismo de conflictos existente.
    """
    confianza_actualizada: dict[str, float] = {}
    discrepancias: dict[str, dict] = {}

    orden_geometria_por_etiqueta = {fila.etiqueta: fila.orden for fila in filas_geometricas}

    con_etiqueta = [
        (var, etiqueta)
        for var, etiqueta in (
            (var, getattr(vv, "etiqueta_fila", None)) for var, vv in variables.items()
        )
        if etiqueta is not None
    ]

    for original_orden, (var, etiqueta) in enumerate(con_etiqueta):
        orden_geometria = orden_geometria_por_etiqueta.get(etiqueta)
        if orden_geometria is None:
            continue  # la geometría no detectó esa etiqueta — no hay con qué contrastar
        if abs(orden_geometria - original_orden) <= tolerancia_orden:
            confianza_actualizada[var] = min(1.0, variables[var].confianza + 0.2)
        else:
            discrepancias[var] = {
                "etiqueta": etiqueta,
                "original_orden": original_orden,
                "orden_geometria": orden_geometria,
            }

    return confianza_actualizada, discrepancias
