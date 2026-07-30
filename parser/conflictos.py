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

from dataclasses import replace
from typing import Any, Optional

from coverage import Conflicto, VariableValue


UMBRAL_EMPATE = 0.1


def _clave_comparable(valor: Any) -> Any:
    """Representación hasheable de un valor para agruparlo por igualdad.

    Variables tipo dict (ej. horas_tarea_manual_semana) o list (ej.
    tareas_sin_backup) no se pueden usar directo como clave de dict porque
    no son hasheables — acá se convierten a una tupla ordenada equivalente,
    sin tocar el valor real que se termina guardando en VariableValue.
    """
    if isinstance(valor, dict):
        return tuple(sorted(valor.items()))
    if isinstance(valor, list):
        return tuple(valor)
    return valor


def _candidato(valor: VariableValue) -> dict:
    return {
        "valor": valor.valor,
        "archivo": valor.archivo_origen,
        "fuente": valor.fuente,
        "confianza": valor.confianza,
    }


def _resolver_por_periodo(candidatos: list[VariableValue], var: str) -> tuple[Optional[VariableValue], Optional[Conflicto]]:
    """
    Cuando TODOS los candidatos de una variable traen `.serie`, comparar
    solo el escalar `.valor` no tiene sentido: dos archivos que cubren
    rangos de meses distintos (ej. uno enero-abril, otro mayo-junio) no
    están compitiendo por el mismo dato, están aportando partes distintas
    de la misma historia — mezclarlos por el `.valor` a secas los haría
    parecer un conflicto cuando no lo es. Acá se resuelve período por
    período (unión de todos los períodos de todos los candidatos) con la
    misma regla de empate que el resto del módulo, y el resultado es una
    serie fusionada + el último período como valor vigente.
    """
    todos_los_periodos: list[str] = []
    for c in candidatos:
        for p in c.serie:
            if p not in todos_los_periodos:
                todos_los_periodos.append(p)

    serie_resuelta: dict[str, Any] = {}
    confianza_por_periodo: dict[str, float] = {}
    fuente_por_periodo: dict[str, str] = {}

    for periodo in todos_los_periodos:
        candidatos_del_periodo = [c for c in candidatos if periodo in c.serie]
        mejor_por_valor: dict[Any, VariableValue] = {}
        for c in candidatos_del_periodo:
            clave = _clave_comparable(c.serie[periodo])
            actual = mejor_por_valor.get(clave)
            if actual is None or c.confianza > actual.confianza:
                mejor_por_valor[clave] = c

        if len(mejor_por_valor) == 1:
            ganador = next(iter(mejor_por_valor.values()))
        else:
            ordenados = sorted(mejor_por_valor.values(), key=lambda c: c.confianza, reverse=True)
            mayor, segunda = ordenados[0], ordenados[1]
            if round(mayor.confianza - segunda.confianza, 9) < UMBRAL_EMPATE:
                # Conflicto real para este período: no se resuelve nada de
                # la variable (misma granularidad que el resto del
                # sistema — un conflicto es por variable, no por período).
                conflicto = Conflicto(
                    variable=var,
                    candidatos=[
                        _candidato(replace(c, valor=c.serie[periodo]))
                        for c in sorted(candidatos_del_periodo, key=lambda c: c.confianza, reverse=True)
                    ],
                )
                return None, conflicto
            ganador = mayor

        serie_resuelta[periodo] = ganador.serie[periodo]
        confianza_por_periodo[periodo] = ganador.confianza
        fuente_por_periodo[periodo] = ganador.fuente

    if not serie_resuelta:
        return None, None
    ultimo = todos_los_periodos[-1]
    resuelto = VariableValue(
        valor=serie_resuelta[ultimo], fuente=fuente_por_periodo[ultimo],
        confianza=confianza_por_periodo[ultimo], serie=serie_resuelta, periodo=ultimo,
    )
    return resuelto, None


def _resolver_por_valor_escalar(candidatos: list[VariableValue], var: str) -> tuple[Optional[VariableValue], Optional[Conflicto]]:
    """Comparar `.valor` a secas — el camino de siempre, para cuando NINGÚN
    candidato trae período (dato de una sola foto, wizard, o un extractor
    que no pudo identificar período). Extraído sin cambios de comportamiento
    para poder reusarlo también como fallback del caso mixto (Fase E, ver
    `resolver_conflictos`) sin duplicar la lógica de empate."""
    mejor_por_valor: dict[Any, VariableValue] = {}
    for c in candidatos:
        clave = _clave_comparable(c.valor)
        mejor_actual = mejor_por_valor.get(clave)
        if mejor_actual is None or c.confianza > mejor_actual.confianza:
            mejor_por_valor[clave] = c

    if len(mejor_por_valor) == 1:
        return next(iter(mejor_por_valor.values())), None

    ordenados = sorted(mejor_por_valor.values(), key=lambda c: c.confianza, reverse=True)
    mayor, segunda = ordenados[0], ordenados[1]
    # round() evita que restas como 0.9 - 0.8 == 0.09999999999999998
    # (error de punto flotante) hagan pasar por "empate" un caso que
    # justo toca el umbral.
    if round(mayor.confianza - segunda.confianza, 9) >= UMBRAL_EMPATE:
        return mayor, None
    return None, Conflicto(
        variable=var,
        candidatos=[_candidato(c) for c in sorted(candidatos, key=lambda c: c.confianza, reverse=True)],
    )


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

        con_serie = [c for c in candidatos if c.serie]
        sin_serie = [c for c in candidatos if not c.serie]

        if not sin_serie:
            # Todas traen serie: resolver período a período, sin cambios.
            resuelto, conflicto = _resolver_por_periodo(candidatos, var)
            if conflicto is not None:
                conflictos.append(conflicto)
            elif resuelto is not None:
                resueltas[var] = resuelto
            continue

        if con_serie:
            # Fase E — caso mixto: al menos una fuente trae fecha y al
            # menos una no. Comparar el `.valor` de la que no tiene fecha
            # contra el VIGENTE de la que sí — sin saber si están hablando
            # del mismo mes — es el bug real que encontró Felipe: el
            # vigente de junio (Excel, con serie) terminaba comparado
            # contra el total de marzo (CSV, sin serie) como si fueran la
            # misma pregunta. Acá primero se resuelven las fuentes CON
            # fecha entre sí (su comparación SÍ es válida, período a
            # período), y sólo después se compara ese resultado contra las
            # que no tienen fecha — nunca al revés.
            resuelto_serie, conflicto_interno = _resolver_por_periodo(con_serie, var)
            if conflicto_interno is not None:
                # Las fuentes CON fecha ya disienten entre sí para algún
                # período — ese es el conflicto real (mismo tipo de
                # siempre, "valores_distintos"); las fuentes sin fecha se
                # anexan sólo como contexto, no cambian la naturaleza del
                # conflicto.
                conflicto_interno.candidatos += [_candidato(c) for c in sin_serie]
                conflictos.append(conflicto_interno)
                continue

            if resuelto_serie is not None:
                discrepantes = [
                    c for c in sin_serie
                    if _clave_comparable(c.valor) != _clave_comparable(resuelto_serie.valor)
                ]
                if not discrepantes:
                    # Coinciden con el vigente: no hay nada que preguntar.
                    resueltas[var] = resuelto_serie
                else:
                    conflictos.append(Conflicto(
                        variable=var,
                        tipo="cobertura_distinta",
                        candidatos=[_candidato(resuelto_serie)] + [_candidato(c) for c in discrepantes],
                    ))
                continue
            # con_serie no resolvió nada (series vacías tras el merge):
            # cae al camino escalar de siempre, comparando TODOS los
            # candidatos — mismo fallback que si nadie tuviera serie.

        # Al menos un candidato no trae serie y (arriba) `con_serie` no
        # aportó nada resoluble, o directamente ningún candidato trae
        # serie: se compara el escalar `.valor` como siempre.
        resuelto, conflicto = _resolver_por_valor_escalar(candidatos, var)
        if conflicto is not None:
            conflictos.append(conflicto)
        elif resuelto is not None:
            resueltas[var] = resuelto

    return resueltas, conflictos
