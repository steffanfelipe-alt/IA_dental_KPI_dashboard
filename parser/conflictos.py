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

from typing import Any, Optional

from coverage import Conflicto, VariableValue
from periodos import orden_cronologico
from trazabilidad import explicar


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
    """Fase I7: antes sólo viajaban 4 claves (valor/archivo/fuente/
    confianza) — la UI no podía mostrar "la cuenta completa" de un
    candidato porque nunca la recibía, aunque el VariableValue sí la
    tenía. Se agregan, siempre que existan: la serie completa (para poder
    ver "esto cubre enero-junio" de un vistazo), el período vigente, las
    etiquetas crudas originales, y el texto de trazabilidad.explicar() —
    la misma explicación que ya usa la sección 2a para los KPIs
    calculados, ahora también para un candidato en conflicto."""
    candidato = {
        "valor": valor.valor,
        "archivo": valor.archivo_origen,
        "fuente": valor.fuente,
        "confianza": valor.confianza,
        "explicacion": explicar(valor),
    }
    if valor.serie:
        candidato["serie"] = dict(valor.serie)
        candidato["periodo_vigente"] = valor.periodo
        if valor.etiquetas_originales:
            candidato["etiquetas_originales"] = dict(valor.etiquetas_originales)
    return candidato


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
    # Fase G1: antes se descartaba el VariableValue ganador entero y sólo
    # se rescataban `fuente`/`confianza` — así se perdía en silencio
    # archivo_origen, trazabilidad y etiquetas_originales para TODA
    # variable con serie, incluso sin conflicto. Guardar el ganador
    # completo por período es lo que permite reconstruirlos abajo.
    ganador_por_periodo: dict[str, VariableValue] = {}

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
                    # I8b (bug E2E): antes se mostraba `c.serie[periodo]` — el
                    # valor del PRIMER período en conflicto (ej. Abril) — pero
                    # la traza de cada candidato describe su vigente (Mayo),
                    # así el título y la explicación se contradecían. Se
                    # muestra `c` tal cual: valor vigente + serie completa,
                    # consistente con la traza. La serie de abajo desempata
                    # cuando dos fuentes coinciden en el vigente pero difieren
                    # en la historia.
                    candidatos=[
                        _candidato(c)
                        for c in sorted(candidatos_del_periodo, key=lambda c: c.confianza, reverse=True)
                    ],
                )
                return None, conflicto
            ganador = mayor

        serie_resuelta[periodo] = ganador.serie[periodo]
        confianza_por_periodo[periodo] = ganador.confianza
        fuente_por_periodo[periodo] = ganador.fuente
        ganador_por_periodo[periodo] = ganador

    if not serie_resuelta:
        return None, None
    # Fase I8: bug encontrado leyendo el código para "elegir los dos" —
    # `todos_los_periodos[-1]` tomaba el último por ORDEN DE APARICIÓN (el
    # orden en que se recorrieron los candidatos y sus series), no
    # cronológico. Si el archivo con jul-dic se procesaba antes que el de
    # ene-jun, el "vigente" resultante era junio, no diciembre.
    ultimo = orden_cronologico(serie_resuelta)[-1]
    ganador_ultimo = ganador_por_periodo[ultimo]

    # `etiquetas_originales`: la etiqueta cruda de cada período la aporta
    # el ganador DE ESE período (no necesariamente el mismo candidato que
    # ganó el último) — es una fusión, no una copia del último candidato.
    etiquetas_fusionadas: dict[str, str] = {}
    for periodo, ganador in ganador_por_periodo.items():
        if ganador.etiquetas_originales and periodo in ganador.etiquetas_originales:
            etiquetas_fusionadas[periodo] = ganador.etiquetas_originales[periodo]

    # `periodos_no_reconocidos`: no está indexado por período canónico
    # (son etiquetas que el parser no supo leer), así que no hay "ganador"
    # posible — se preserva la unión de TODOS los candidatos, ganadores o
    # no, para que ningún período ilegible de ningún archivo se pierda.
    no_reconocidos_fusionados: dict[str, Any] = {}
    for c in candidatos:
        if c.periodos_no_reconocidos:
            no_reconocidos_fusionados.update(c.periodos_no_reconocidos)

    resuelto = VariableValue(
        valor=serie_resuelta[ultimo], fuente=fuente_por_periodo[ultimo],
        confianza=confianza_por_periodo[ultimo], serie=serie_resuelta, periodo=ultimo,
        archivo_origen=ganador_ultimo.archivo_origen,
        trazabilidad=ganador_ultimo.trazabilidad,
        etiquetas_originales=etiquetas_fusionadas or None,
        periodos_no_reconocidos=no_reconocidos_fusionados or None,
    )
    return resuelto, None


def fusionar_candidatos(candidatos: list[dict], periodos_de_escalares: Optional[dict[int, str]] = None) -> dict:
    """Fase I8 ("elegir los dos"): fusiona 1+ candidatos — en la misma
    forma que arma `_candidato()`, con `serie`/`etiquetas_originales` si
    las tienen — en un solo valor con su serie combinada, en vez de forzar
    a elegir uno solo y descartar el resto.

    Con un único candidato, esto de paso arregla un bug real:
    `pipeline.resolver_conflicto` construía siempre un `VariableValue`
    escalar pelado al confirmar, aunque el candidato elegido tuviera 6
    meses de historia — la serie se perdía en el mismo movimiento que
    "ganaba" el conflicto. Acá se preserva.

    `periodos_de_escalares`: `{índice_en_candidatos: período}` — un
    candidato SIN serie propia (el caso "cobertura_distinta": un total
    sin fecha) no tiene forma de saber a qué mes corresponde sin que el
    dueño de la clínica lo diga. Sin esa asignación explícita, ese
    candidato no aporta a la serie fusionada — nunca se inventa un
    período (mismo principio que el resto del módulo)."""
    serie_fusionada: dict[str, Any] = {}
    etiquetas_fusionadas: dict[str, str] = {}
    for i, cand in enumerate(candidatos):
        if cand.get("serie"):
            serie_fusionada.update(cand["serie"])
            if cand.get("etiquetas_originales"):
                etiquetas_fusionadas.update(cand["etiquetas_originales"])
        elif periodos_de_escalares and i in periodos_de_escalares:
            serie_fusionada[periodos_de_escalares[i]] = cand["valor"]

    if not serie_fusionada:
        # Ningún candidato tenía serie ni período asignado: no hay nada
        # que fusionar con sentido — se usa el último tal cual (mismo
        # resultado que "elegir uno", sin inventar una fecha).
        ultimo = candidatos[-1]
        return {"valor": ultimo["valor"], "serie": None, "periodo": None, "etiquetas_originales": None}

    periodo_vigente = orden_cronologico(serie_fusionada)[-1]
    return {
        "valor": serie_fusionada[periodo_vigente],
        "serie": serie_fusionada,
        "periodo": periodo_vigente,
        "etiquetas_originales": etiquetas_fusionadas or None,
    }


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
            # Fase H1: el valor confirmado por el dueño sigue ganando
            # siempre — no se auto-resuelve en silencio ni se pierde la
            # confirmación previa (decisión de Felipe). Lo que cambia acá
            # es que ahora se avisa si algún candidato la contradice, en
            # vez de tragárselo callado como antes.
            otros = [c for c in candidatos if c is not confirmado]
            discrepantes = [c for c in otros if _clave_comparable(c.valor) != _clave_comparable(confirmado.valor)]
            if discrepantes:
                conflictos.append(Conflicto(
                    variable=var,
                    tipo="contradice_confirmado",
                    candidatos=[_candidato(confirmado)] + [_candidato(c) for c in discrepantes],
                ))
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
