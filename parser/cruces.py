"""
cruces.py

Fase B del plan de evolución: métricas derivadas fuera de las 20
KPIFormula fijas. El catálogo de schema.py es cerrado por diseño — cada
fórmula corresponde 1:1 a la tabla del Miro (ver docstring de ese módulo)
— así que ningún cruce entre variables de hojas distintas existe hoy,
aunque ambas estén cargadas con serie histórica alineada. Caso real:
monto_cobrado (hoja Financiero) ÷ pacientes_atendidos_periodo (hoja
Resumen) muestra +19,8% de enero a junio y hoy es invisible.

Dos capas, ambas deterministas, sin llamar a la API ni al modelo:

  1. `generar_cruces_embudo` — usa `schema.ETAPAS_EMBUDO`, el orden del
     embudo declarado una sola vez. Toda razón etapa_posterior /
     etapa_anterior es una tasa de conversión válida por construcción.
  2. `generar_cruces_algebraicos` — usa `schema.OPERACIONES_LEGALES`,
     análisis dimensional puro sobre `unidad_dato` (ya declarada para cada
     variable en METRICAS). Filtra por construcción cualquier combinación
     sin interpretación — ej. `resenas_nuevas ÷ no_shows` es
     dimensionalmente "válido" (conteo/conteo) pero semánticamente basura;
     por eso el conteo/conteo generérico se excluye acá y queda 100% en
     manos de la capa 1, que sólo lo permite entre etapas del embudo.

Un `Cruce` NO es un KPI: no tiene `kpi_id`, no entra a `coverage.py`,
`diagnostico.py` ni `priorizacion.py`. Sin benchmark,
`diagnostico.evaluar_estado` ya confina cualquier cosa sin benchmark a
WATCH — un cruce nunca puede decir "esto está mal contra el mercado",
sólo "esto se movió X% en N períodos". Es la propiedad correcta y no se
fuerza acá. `pipeline.py` lo expone en una clave aparte
(`resultado["cruces"]`), y `probar_manual.py` lo muestra en su propia
sección, nunca mezclado con "KPIs calculados".
"""

from dataclasses import dataclass
from typing import Optional

from catalogo_tecnologico import INTERVENCIONES
from schema import (
    DENOMINADORES_VOLUMEN,
    ETAPAS_EMBUDO,
    KPI_FORMULAS,
    METRICAS,
    OPERACIONES_LEGALES,
    VARIABLE_TYPES,
)

# Un cruce con un solo período común no muestra tendencia, muestra un punto
# — no hay "se movió" que reportar con un solo dato.
MINIMO_PERIODOS_COMUNES = 2

# Techo por defecto de cuántos cruces devuelve `generar_cruces`. El espacio
# de combinaciones de la capa 2 crece con el cuadrado del número de
# variables cargadas; sin techo, una migración con muchas variables
# financieras inundaría la UI de cruces de relevancia marginal. Es
# ajustable (None = sin techo) para no atarlo a una decisión de UI.
LIMITE_DEFAULT = 20


@dataclass
class Cruce:
    nombre: str
    variable_a: str
    operacion: str  # "/" | "-"
    variable_b: str
    unidad: str
    valor: float  # último período común
    serie: dict[str, float]
    periodos_comunes: int
    confianza: float  # min(confianza de los insumos)
    origen: str  # "embudo" | "algebra" | "propuesto"
    justificacion: str
    # Fase F: sólo la capa 3 (cruces_propuestos.py) los completa, vía
    # replace() después de calcular_cruce — las capas 1/2 de acá nunca los
    # setean y quedan en "" (un cruce determinístico no necesita que el
    # modelo le explique en qué etapa del embudo actúa: ya lo sabemos por
    # construcción).
    etapa_embudo: str = ""
    impacto_decision: str = ""


# Pares (numerador, denominador) que alguna de las 21 KPIFormula ya calcula
# — un cruce que reproduce exactamente ese par se descarta en
# `generar_cruces`, para no duplicar un KPI que ya existe con otro nombre.
_PARES_YA_EN_CATALOGO: set[tuple[str, str]] = {
    (kpi.numerador, kpi.denominador) for kpi in KPI_FORMULAS if kpi.numerador and kpi.denominador
}

# Variables que el catálogo de intervenciones ya señala como objetivo de
# alguna oportunidad tecnológica — señal de ranking, no filtro (ver
# schema.py: Intervencion.metrica_objetivo es texto libre y no matchea;
# kpi_objetivo/variable_objetivo son los campos duros).
_VARIABLES_OBJETIVO_CATALOGO: set[str] = {
    i.variable_objetivo for i in INTERVENCIONES if i.variable_objetivo
}

# Capa 2 nunca toca conteo÷conteo genérico: esa combinación queda 100% en
# manos de la capa 1 (embudo), que la restringe a pares que respetan el
# orden declarado. Sin esta exclusión, ambas capas producirían el mismo
# cruce por caminos distintos.
_OPERACIONES_ALGEBRA = {
    clave: unidad for clave, unidad in OPERACIONES_LEGALES.items() if clave != ("conteo", "/", "conteo")
}


def _nombre_humano(variable: str) -> str:
    info = METRICAS.get(variable)
    return info.nombre_humano if info else variable


def _series_comunes(vv_a, vv_b) -> Optional[dict[str, tuple[float, float]]]:
    """Misma lógica de intersección que `coverage._calcular_serie_kpi`,
    replicada acá a propósito — `coverage.py` no se importa ni se toca
    (ver docstring del módulo). Devuelve {período: (valor_a, valor_b)}
    sólo para los períodos que ambas series traen, en el orden de
    aparición de la serie de A."""
    serie_a, serie_b = getattr(vv_a, "serie", None), getattr(vv_b, "serie", None)
    if not serie_a or not serie_b:
        return None
    comunes = set(serie_a) & set(serie_b)
    if not comunes:
        return None
    orden = [p for p in serie_a if p in comunes]
    return {p: (serie_a[p], serie_b[p]) for p in orden}


def _aplicar(operacion: str, a: float, b: float, unidad: str) -> Optional[float]:
    """None cuando la operación no da un resultado válido para ESE
    período puntual (denominador 0) — se salta ese período, igual que
    `schema._pct` con un KPI porcentual. Nunca se inventa un valor."""
    if operacion == "/":
        if not b:
            return None
        valor = a / b
        # "%" es la unidad declarada para conteo/conteo y monto/monto en
        # OPERACIONES_LEGALES — misma convención 0-100 que schema._pct,
        # no 0-1.
        return round(valor * 100, 1) if unidad == "%" else round(valor, 2)
    if operacion == "-":
        return round(a - b, 2)
    raise ValueError(f"operación desconocida: {operacion!r}")


def calcular_cruce(
    nombre: str, var_a: str, operacion: str, var_b: str, unidad: str,
    vv_a, vv_b, origen: str, justificacion: str,
) -> Optional[Cruce]:
    """Intenta armar un Cruce entre dos VariableValue ya presentes. None si
    no hay series, no llegan al mínimo de períodos comunes, o ningún
    período del solapamiento produce un valor válido (denominador 0 en
    todos)."""
    pares = _series_comunes(vv_a, vv_b)
    if pares is None or len(pares) < MINIMO_PERIODOS_COMUNES:
        return None

    serie: dict[str, float] = {}
    for periodo, (a, b) in pares.items():
        valor = _aplicar(operacion, a, b, unidad)
        if valor is not None:
            serie[periodo] = valor
    if len(serie) < MINIMO_PERIODOS_COMUNES:
        return None

    ultimo = list(serie.keys())[-1]
    confianza_a = getattr(vv_a, "confianza", 1.0)
    confianza_b = getattr(vv_b, "confianza", 1.0)
    return Cruce(
        nombre=nombre, variable_a=var_a, operacion=operacion, variable_b=var_b,
        unidad=unidad, valor=serie[ultimo], serie=serie, periodos_comunes=len(serie),
        confianza=round(min(confianza_a, confianza_b), 4),
        origen=origen, justificacion=justificacion,
    )


def generar_cruces_embudo(variables: dict) -> list[Cruce]:
    """Capa 1: toda razón etapa_posterior / etapa_anterior sobre
    `ETAPAS_EMBUDO`. No filtra contra el catálogo acá — eso lo hace
    `generar_cruces` una sola vez, para las dos capas juntas."""
    cruces = []
    for i, etapa_anterior in enumerate(ETAPAS_EMBUDO):
        for etapa_posterior in ETAPAS_EMBUDO[i + 1:]:
            if etapa_anterior not in variables or etapa_posterior not in variables:
                continue
            cruce = calcular_cruce(
                nombre=f"Conversión: {_nombre_humano(etapa_anterior)} → {_nombre_humano(etapa_posterior)}",
                var_a=etapa_posterior, operacion="/", var_b=etapa_anterior, unidad="%",
                vv_a=variables[etapa_posterior], vv_b=variables[etapa_anterior],
                origen="embudo",
                justificacion=(
                    f"'{etapa_anterior}' y '{etapa_posterior}' son etapas del embudo declarado "
                    f"(schema.ETAPAS_EMBUDO) — toda razón etapa posterior / etapa anterior es una "
                    f"tasa de conversión válida por construcción, aunque no sean etapas consecutivas."
                ),
            )
            if cruce:
                cruces.append(cruce)
    return cruces


def _candidatas_por_unidad(variables: dict, unidad_dato: str) -> list[str]:
    """Variables escalares presentes con esa `unidad_dato` — sólo int/float,
    nunca dict/list/ledger (esos no tienen una aritmética escalar legal)."""
    return sorted(
        v for v in variables
        if v in METRICAS and METRICAS[v].unidad_dato == unidad_dato and VARIABLE_TYPES.get(v) in ("int", "float")
    )


def generar_cruces_algebraicos(variables: dict) -> list[Cruce]:
    """Capa 2: análisis dimensional puro sobre `OPERACIONES_LEGALES`
    (menos conteo÷conteo, exclusivo de la capa 1). No filtra contra el
    catálogo acá — eso lo hace `generar_cruces` una sola vez."""
    cruces = []
    montos = _candidatas_por_unidad(variables, "monto_ars")
    conteos = _candidatas_por_unidad(variables, "conteo")
    horas = _candidatas_por_unidad(variables, "horas")
    # Fase G4: monto÷conteo sólo tiene sentido si el conteo es una base de
    # volumen (turnos, presupuestos, pacientes) — "Monto cobrado por
    # No-shows" no es una métrica, no_shows nunca es un denominador. Mismo
    # criterio que ETAPAS_EMBUDO para conteo÷conteo, aplicado acá.
    conteos_volumen = [c for c in conteos if c in DENOMINADORES_VOLUMEN]

    # monto ÷ conteo -> $/unidad (ej. ingreso por paciente atendido)
    if ("monto_ars", "/", "conteo") in _OPERACIONES_ALGEBRA:
        unidad = _OPERACIONES_ALGEBRA[("monto_ars", "/", "conteo")]
        for m in montos:
            for c in conteos_volumen:
                cruce = calcular_cruce(
                    nombre=f"{_nombre_humano(m)} por {_nombre_humano(c)}",
                    var_a=m, operacion="/", var_b=c, unidad=unidad,
                    vv_a=variables[m], vv_b=variables[c], origen="algebra",
                    justificacion=f"'{m}' es un monto en ARS y '{c}' es un conteo — la razón es $/unidad, dimensionalmente válida.",
                )
                if cruce:
                    cruces.append(cruce)

    # monto ÷ horas -> $/hora (ej. producción por hora-sillón, fuera de las
    # variables ya cubiertas por el KPI 12 si ese par específico coincide —
    # el filtro de catálogo lo saca en generar_cruces)
    if ("monto_ars", "/", "horas") in _OPERACIONES_ALGEBRA:
        unidad = _OPERACIONES_ALGEBRA[("monto_ars", "/", "horas")]
        for m in montos:
            for h in horas:
                cruce = calcular_cruce(
                    nombre=f"{_nombre_humano(m)} por {_nombre_humano(h)}",
                    var_a=m, operacion="/", var_b=h, unidad=unidad,
                    vv_a=variables[m], vv_b=variables[h], origen="algebra",
                    justificacion=f"'{m}' es un monto en ARS y '{h}' son horas — la razón es $/hora.",
                )
                if cruce:
                    cruces.append(cruce)

    # conteo ÷ horas -> unidades/hora
    if ("conteo", "/", "horas") in _OPERACIONES_ALGEBRA:
        unidad = _OPERACIONES_ALGEBRA[("conteo", "/", "horas")]
        for c in conteos:
            for h in horas:
                cruce = calcular_cruce(
                    nombre=f"{_nombre_humano(c)} por {_nombre_humano(h)}",
                    var_a=c, operacion="/", var_b=h, unidad=unidad,
                    vv_a=variables[c], vv_b=variables[h], origen="algebra",
                    justificacion=f"'{c}' es un conteo y '{h}' son horas — la razón es unidades/hora.",
                )
                if cruce:
                    cruces.append(cruce)

    # monto ÷ monto -> % (ej. overhead, tasa de cobro); monto − monto -> $
    # (ej. resultado operativo). Mismo tipo en ambos lados: se recorre con
    # `montos[i+1:]` para no generar el par espejado (a÷b y b÷a) como si
    # fueran dos cruces distintos.
    for i, a in enumerate(montos):
        for b in montos[i + 1:]:
            if ("monto_ars", "/", "monto_ars") in _OPERACIONES_ALGEBRA:
                # La división no tiene el problema de la resta (nunca da
                # negativo si divide algo por sí mismo o algo mayor), así
                # que acá sí queda el orden alfabético — es arbitrario,
                # pero el nombre del cruce siempre deja explícito quién es
                # cada lado.
                unidad = _OPERACIONES_ALGEBRA[("monto_ars", "/", "monto_ars")]
                cruce = calcular_cruce(
                    nombre=f"{_nombre_humano(a)} / {_nombre_humano(b)}",
                    var_a=a, operacion="/", var_b=b, unidad=unidad,
                    vv_a=variables[a], vv_b=variables[b], origen="algebra",
                    justificacion=f"'{a}' y '{b}' son ambos montos en ARS — la razón es un %.",
                )
                if cruce:
                    cruces.append(cruce)
            if ("monto_ars", "-", "monto_ars") in _OPERACIONES_ALGEBRA:
                # Fase G4: antes elegía la dirección alfabéticamente, así
                # que la mitad de las restas terminaban en negativo y se
                # leían como si algo estuviera mal (ej. "Costo por
                # hora-sillón − Monto cobrado = $-2.660.000"). Ahora el
                # monto mayor (por su valor vigente) va como minuendo, para
                # que el resultado sea positivo cuando tiene sentido serlo.
                unidad = _OPERACIONES_ALGEBRA[("monto_ars", "-", "monto_ars")]
                mayor, menor = (a, b) if variables[a].valor >= variables[b].valor else (b, a)
                cruce = calcular_cruce(
                    nombre=f"{_nombre_humano(mayor)} − {_nombre_humano(menor)}",
                    var_a=mayor, operacion="-", var_b=menor, unidad=unidad,
                    vv_a=variables[mayor], vv_b=variables[menor], origen="algebra",
                    justificacion=(
                        f"'{mayor}' y '{menor}' son ambos montos en ARS — la resta es un monto en ARS "
                        f"(el mayor de los dos como minuendo, para que el resultado sea positivo)."
                    ),
                )
                if cruce:
                    cruces.append(cruce)

    return cruces


def _variacion_relativa(cruce: Cruce) -> float:
    """|último - primero| / primero, sobre la serie del cruce. Sirve para
    priorizar cruces que efectivamente se movieron por sobre los que están
    planos — un cruce plano en 6 meses es mucho menos accionable."""
    valores = list(cruce.serie.values())
    if len(valores) < 2 or not valores[0]:
        return 0.0
    return abs((valores[-1] - valores[0]) / valores[0])


def _score(cruce: Cruce) -> tuple:
    relevante = cruce.variable_a in _VARIABLES_OBJETIVO_CATALOGO or cruce.variable_b in _VARIABLES_OBJETIVO_CATALOGO
    return (int(relevante), cruce.periodos_comunes, round(_variacion_relativa(cruce), 4))


def generar_cruces(variables: dict, limite: Optional[int] = LIMITE_DEFAULT) -> list[Cruce]:
    """Orquestador: junta las dos capas, saca los pares que el catálogo de
    21 KPIs ya calcula por otro nombre, y ordena por relevancia (¿el
    catálogo de intervenciones ya la señala como objetivo? ¿cuántos
    períodos comunes tiene? ¿cuánto se movió?) — más relevante primero.
    `limite=None` devuelve todo, sin techo."""
    candidatos = generar_cruces_embudo(variables) + generar_cruces_algebraicos(variables)
    filtrados = [
        c for c in candidatos
        if (c.variable_a, c.variable_b) not in _PARES_YA_EN_CATALOGO
    ]
    filtrados.sort(key=_score, reverse=True)
    return filtrados if limite is None else filtrados[:limite]
