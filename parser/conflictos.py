"""
conflictos.py

Cuando dos fuentes (archivos migrados, o una migración anterior + una
nueva) dan valores distintos para la misma variable y ninguna es
claramente más confiable que la otra, no hay forma correcta de elegir en
automático — el comportamiento correcto es mostrarle el conflicto al
dueño de la clínica y que decida él, no elegir por orden de llegada.

Separado de pipeline.py para poder testear la lógica de resolución sin
depender de los extractores ni de Claude.
"""

from typing import Any

from coverage import Conflicto, VariableValue


UMBRAL_EMPATE = 0.1


def _candidato(valor: VariableValue) -> dict:
    return {
        "valor": valor.valor,
        "archivo": valor.archivo_origen,
        "fuente": valor.fuente,
        "confianza": valor.confianza,
    }


def resolver_conflictos(
    fuentes: list[dict[str, VariableValue]],
) -> tuple[dict[str, VariableValue], list[Conflicto]]:
    """
    Agrupa todos los candidatos por variable a través de todas las fuentes.
    Devuelve (variables_resueltas, conflictos_pendientes).

    Una variable con fuente == "confirmado_por_dueno" en cualquiera de las
    fuentes gana siempre y no entra en la lógica de empate.
    """
    candidatos_por_variable: dict[str, list[VariableValue]] = {}
    for fuente in fuentes:
        for var, valor in fuente.items():
            candidatos_por_variable.setdefault(var, []).append(valor)

    resueltas: dict[str, VariableValue] = {}
    conflictos: list[Conflicto] = []

    for var, candidatos in candidatos_por_variable.items():
        confirmado = next((c for c in candidatos if c.fuente == "confirmado_por_dueno"), None)
        if confirmado is not None:
            # TODO: si un archivo nuevo contradice un valor ya confirmado por
            # el dueño, hoy se ignora silenciosamente y gana la confirmación
            # previa. Falta abrir un conflicto nuevo para ese caso puntual
            # (fuera de alcance de este plan).
            resueltas[var] = confirmado
            continue

        # Mejor candidato por cada valor distinto propuesto — así, si dos
        # archivos ya están de acuerdo en un valor, no importa que un
        # tercero (con menos confianza) proponga otra cosa distinta.
        mejor_por_valor: dict[Any, VariableValue] = {}
        for c in candidatos:
            mejor_actual = mejor_por_valor.get(c.valor)
            if mejor_actual is None or c.confianza > mejor_actual.confianza:
                mejor_por_valor[c.valor] = c

        if len(mejor_por_valor) == 1:
            resueltas[var] = next(iter(mejor_por_valor.values()))
            continue

        ordenados = sorted(mejor_por_valor.values(), key=lambda c: c.confianza, reverse=True)
        mayor, segunda = ordenados[0], ordenados[1]
        # round() evita que restas como 0.9 - 0.8 == 0.09999999999999998
        # (error de punto flotante) hagan pasar por "empate" un caso que
        # justo toca el umbral.
        if round(mayor.confianza - segunda.confianza, 9) >= UMBRAL_EMPATE:
            resueltas[var] = mayor
        else:
            conflictos.append(Conflicto(
                variable=var,
                candidatos=[_candidato(c) for c in sorted(candidatos, key=lambda c: c.confianza, reverse=True)],
            ))

    return resueltas, conflictos
