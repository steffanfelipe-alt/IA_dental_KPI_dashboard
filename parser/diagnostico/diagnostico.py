"""
diagnostico.py

Fase 4 del plan de evolución — la prioridad #1 del Documento Maestro de
Evolución. Se inserta entre priorizacion.py e interpretacion.py:

    coverage.py -> priorizacion.py -> diagnostico.py -> interpretacion.py

No redacta nada (eso lo sigue haciendo Claude en interpretacion.py). Este
módulo estructura qué sabe el sistema, qué infiere, qué sospecha y qué
desconoce — determinista y auditable, sin llamar a la API.

## Por qué existe

`interpretacion.SYSTEM_PROMPT_BASE` ya tenía esta lógica, pero como PROSA
dentro del prompt (reglas 2 y 8): "si el contexto contradice el número,
señalá la contradicción", "aceptación alta + ticket bajo = problema de
mix". Vivir solo en texto natural la vuelve imposible de auditar o testear
sin llamar a Claude. Este módulo mueve esas dos reglas a datos —
`PATRONES_CRUZADOS` y `detectar_contradicciones` — y la regla 8 del prompt
se retira una vez que este módulo aterriza (ver interpretacion.py), para
que no queden dos versiones de la misma lógica pudiendo divergir.

## Separar anomalía, diagnóstico y causa (§7.1 del Documento Maestro)

Un KPI fuera de rango es una ANOMALÍA (dato). Que corresponda a un
problema real de la clínica es un DIAGNÓSTICO (interpretación). Por qué
ocurre es una CAUSA/HIPÓTESIS (probable, no confirmada). No se mezclan:
`Diagnostico.anomalias` son hechos, `Diagnostico.hipotesis` son
conjeturas explícitamente marcadas como tales, `Diagnostico.estado` nunca
es más seguro de lo que los datos permiten (ver `EstadoEvidencia`).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from parser.diagnostico.benchmarks import Gap, calcular_gap
from parser.diagnostico.calidad import suficiencia_datos
from parser.diagnostico.contexto_cualitativo import construir_contexto_cualitativo
from parser.diagnostico.estacionalidad import mes_en_temporada_declarada
from parser.vocabulario.schema import KPI_BY_ID

# Fase G6 (excepción marcada — ver plan): los dos KPIs que el docstring de
# estacionalidad.py nombra explícitamente como afectados por la
# estacionalidad turística de Mar del Plata — no-show (la agenda se
# desordena antes del pico) y producción por hora-sillón (menos gente
# atendida en temporada baja).
KPIS_CON_ESTACIONALIDAD = {4, 12}


class EstadoEvidencia(str, Enum):
    HEALTHY = "HEALTHY"                              # evidencia suficiente de desempeño saludable
    NORMAL = "NORMAL"                                 # dentro de un rango razonable
    WATCH = "WATCH"                                   # señal de atención, sin evidencia suficiente para más
    PROBLEM = "PROBLEM"                               # problema respaldado por evidencia suficiente
    CRITICAL = "CRITICAL"                             # problema grave y prioritario
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"   # no hay evidencia suficiente para afirmar nada


# Umbrales deliberadamente conservadores: es más barato subestimar la
# severidad de un KPI (queda en WATCH) que sobrestimarla (CRITICAL falso,
# que el §2 principio de diseño del Documento Maestro prohíbe: "no inventar
# causalidad").
UMBRAL_MAGNITUD_CRITICO = 50.0
UMBRAL_MAGNITUD_PROBLEMA = 20.0
CONFIABILIDADES_FIRMES = {"oficial", "consultora_ar"}
SUFICIENCIA_MINIMA_PARA_CRITICAL = 0.7


def evaluar_estado(gap: Gap, suficiencia: Optional[float] = None, tiene_serie: bool = False) -> EstadoEvidencia:
    """Determinista: nunca llama a Claude. La firmeza del benchmark
    (`confiabilidad`) y la suficiencia de datos (Fase 3, variables
    derivadas vs. observadas) limitan qué tan severo puede declararse un
    estado — un problema grande medido con un proxy débil o una variable
    despejada de una tasa nunca llega a CRITICAL."""
    if not gap.tiene_benchmark:
        # Sin benchmark: solo la tendencia propia (si hay serie) da algo
        # de señal, y nunca lo suficiente para PROBLEM/CRITICAL — no hay
        # ancla externa contra la cual afirmar severidad.
        return EstadoEvidencia.WATCH if tiene_serie else EstadoEvidencia.INSUFFICIENT_EVIDENCE

    if gap.direccion == "dentro_de_rango" or gap.favorable:
        return EstadoEvidencia.HEALTHY

    magnitud = gap.magnitud_pct or 0.0
    confiable = gap.benchmark is not None and gap.benchmark.confiabilidad in CONFIABILIDADES_FIRMES

    if suficiencia is not None and suficiencia < SUFICIENCIA_MINIMA_PARA_CRITICAL:
        return EstadoEvidencia.PROBLEM if magnitud >= UMBRAL_MAGNITUD_PROBLEMA else EstadoEvidencia.WATCH

    if magnitud >= UMBRAL_MAGNITUD_CRITICO and confiable:
        return EstadoEvidencia.CRITICAL
    if magnitud >= UMBRAL_MAGNITUD_PROBLEMA:
        return EstadoEvidencia.PROBLEM
    return EstadoEvidencia.WATCH


@dataclass
class Anomalia:
    kpi_id: int
    estado: EstadoEvidencia
    magnitud_pct: Optional[float]
    confiabilidad_benchmark: str


@dataclass
class Contradiccion:
    kpi_id: int
    descripcion: str
    preguntas_involucradas: list[str] = field(default_factory=list)


@dataclass
class Hipotesis:
    kpi_id: int
    causa_probable: str
    confianza: str  # "alta" | "media" | "baja"
    preguntas_que_la_sustentan: list[str] = field(default_factory=list)


@dataclass
class Diagnostico:
    kpi_id: int
    problema: str
    estado: EstadoEvidencia
    hechos: list[str]
    anomalias: list[Anomalia]
    hipotesis: list[Hipotesis]
    contradicciones: list[Contradiccion]
    patrones_cruzados: list[str]
    informacion_faltante: list[str]
    confianza: float
    prioridad: Optional[float] = None


# ---------------------------------------------------------------------------
# Patrones cruzados entre KPIs (regla 8 de interpretacion.SYSTEM_PROMPT_BASE,
# movida acá para que sea auditable/testeable sin llamar a Claude)
# ---------------------------------------------------------------------------

def _alto_favorable(gap: Optional[Gap]) -> bool:
    return bool(gap and gap.tiene_benchmark and gap.direccion == "por_encima" and gap.favorable)


def _alto_desfavorable(gap: Optional[Gap]) -> bool:
    return bool(gap and gap.tiene_benchmark and gap.direccion == "por_encima" and not gap.favorable)


def _bajo_desfavorable(gap: Optional[Gap]) -> bool:
    return bool(gap and gap.tiene_benchmark and gap.direccion == "por_debajo" and not gap.favorable)


def _regla_mix_no_cierre(gaps: dict, variables: Optional[dict]) -> bool:
    return _alto_favorable(gaps.get(5)) and _bajo_desfavorable(gaps.get(6))


def _regla_agendamiento_sin_compromiso(gaps: dict, variables: Optional[dict]) -> bool:
    return _alto_favorable(gaps.get(3)) and _alto_desfavorable(gaps.get(4))


def _regla_produccion_baja_con_ocupacion_alta(gaps: dict, variables: Optional[dict]) -> bool:
    if not _bajo_desfavorable(gaps.get(12)) or not variables:
        return False
    ocupadas = variables.get("horas_sillon_ocupadas")
    disponibles = variables.get("horas_sillon_disponibles")
    if ocupadas is None or disponibles is None or not disponibles.valor:
        return False
    return (ocupadas.valor / disponibles.valor) >= 0.8


@dataclass
class PatronCruzado:
    kpis_involucrados: tuple
    regla: Callable[[dict, Optional[dict]], bool]
    conclusion: str


PATRONES_CRUZADOS: list[PatronCruzado] = [
    PatronCruzado(
        (5, 6), _regla_mix_no_cierre,
        "Aceptación de presupuestos alta pero ticket promedio bajo: probable problema de mix de "
        "tratamientos, no de cómo se cierra la venta.",
    ),
    PatronCruzado(
        (3, 4), _regla_agendamiento_sin_compromiso,
        "Tasa de agendamiento alta pero no-show también alto: se está agendando gente que no está "
        "realmente comprometida — revisar el proceso de confirmación de turnos.",
    ),
    PatronCruzado(
        (12,), _regla_produccion_baja_con_ocupacion_alta,
        "Producción por hora-sillón baja con ocupación alta: problema de mix de tratamientos o de "
        "ticket, no de que sobre capacidad ociosa.",
    ),
]


def detectar_patrones_cruzados(gaps: dict[int, Gap], variables: Optional[dict] = None) -> list[dict]:
    return [
        {"kpis_involucrados": patron.kpis_involucrados, "conclusion": patron.conclusion}
        for patron in PATRONES_CRUZADOS
        if patron.regla(gaps, variables)
    ]


# ---------------------------------------------------------------------------
# Contradicciones (regla 2 de interpretacion.SYSTEM_PROMPT_BASE)
# ---------------------------------------------------------------------------

# Heurística deliberadamente simple sobre texto libre (P2 no es una
# respuesta estructurada) — un keyword-match es frágil por definición,
# documentado como tal. Detecta el caso motivador exacto del §20 del
# Documento Maestro: "la clínica dice que confirma automático" vs. "el
# dato muestra no-show alto".
_PALABRAS_CONFIRMACION_AUTOMATICA = ("automátic", "automatic", "recordatorio", "bot", "sistema de confirmacion", "sistema de confirmación")


def _ya_confirma_turnos_automatico(respuestas: dict[str, str]) -> bool:
    p2 = respuestas.get("P2", "").lower()
    return any(palabra in p2 for palabra in _PALABRAS_CONFIRMACION_AUTOMATICA)


def detectar_contradicciones(gaps: dict[int, Gap], respuestas: dict[str, str]) -> list[Contradiccion]:
    contradicciones = []
    if _alto_desfavorable(gaps.get(4)) and _ya_confirma_turnos_automatico(respuestas):
        contradicciones.append(Contradiccion(
            kpi_id=4,
            descripcion=(
                "La clínica declaró que ya confirma turnos de forma automática (P2), pero el no-show "
                "sigue por encima del benchmark. El problema probablemente no es falta de recordatorio "
                "— investigar tipo de paciente, anticipación del turno, canal de confirmación, o precio, "
                "antes de recomendar una automatización que ya existe."
            ),
            preguntas_involucradas=["P2"],
        ))
    return contradicciones


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------

def diagnosticar(
    kpis_calculados: dict[int, dict],
    respuestas_diagnostico: dict[str, str],
    variables: Optional[dict] = None,
) -> list[Diagnostico]:
    """`kpis_calculados`: el dict que devuelve pipeline.procesar_migracion
    (kpi_id -> {"valor", "unidad", "confianza", "serie", ...}). `variables`
    (opcional): el dict crudo de VariableValue — habilita el patrón que
    necesita horas_sillon_ocupadas/disponibles y el cálculo de suficiencia
    de datos (Fase 3) por KPI."""
    gaps: dict[int, Gap] = {}
    for kpi_id, info in kpis_calculados.items():
        valor = info.get("valor")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            gaps[kpi_id] = calcular_gap(kpi_id, valor)

    patrones = detectar_patrones_cruzados(gaps, variables)
    contradicciones = detectar_contradicciones(gaps, respuestas_diagnostico)

    diagnosticos = []
    for kpi_id, gap in gaps.items():
        info = kpis_calculados[kpi_id]
        suficiencia = suficiencia_datos(kpi_id, variables) if variables else None
        estado = evaluar_estado(gap, suficiencia=suficiencia, tiene_serie=bool(info.get("serie")))

        contradicciones_kpi = [c for c in contradicciones if c.kpi_id == kpi_id]
        patrones_kpi = [p["conclusion"] for p in patrones if kpi_id in p["kpis_involucrados"]]

        anomalias = []
        if estado not in (EstadoEvidencia.HEALTHY, EstadoEvidencia.INSUFFICIENT_EVIDENCE):
            anomalias.append(Anomalia(
                kpi_id=kpi_id, estado=estado, magnitud_pct=gap.magnitud_pct,
                confiabilidad_benchmark=gap.benchmark.confiabilidad if gap.benchmark else "sin_benchmark",
            ))

        informacion_faltante = []
        if estado == EstadoEvidencia.INSUFFICIENT_EVIDENCE:
            informacion_faltante.append(
                f"KPI {kpi_id}: sin benchmark ni serie histórica propia — no alcanza evidencia para diagnosticar."
            )

        hipotesis = []
        contexto = construir_contexto_cualitativo(respuestas_diagnostico, kpi_id=kpi_id)
        if anomalias and not contradicciones_kpi and "(sin respuestas cualitativas" not in contexto:
            hipotesis.append(Hipotesis(
                kpi_id=kpi_id,
                causa_probable="ver contexto cualitativo asociado a este KPI",
                confianza="media",
                preguntas_que_la_sustentan=[
                    l.split(":")[0].strip("- ") for l in contexto.splitlines() if l.startswith("-")
                ],
            ))

        # Fase G6 (excepción marcada): señal determinista de estacionalidad
        # en vez de depender de que el modelo se acuerde de aplicar la
        # regla 5 de interpretacion.SYSTEM_PROMPT_BASE a partir de una
        # respuesta de texto libre (P51). Puramente aditivo — una
        # hipótesis más, nunca cambia `estado` ni ningún otro campo.
        if anomalias and kpi_id in KPIS_CON_ESTACIONALIDAD:
            serie_kpi = info.get("serie")
            periodo_vigente = list(serie_kpi)[-1] if serie_kpi else None
            # None si P51 no está respondida (mes_en_temporada_declarada
            # ya maneja eso) — en ausencia de dato no se asume nada.
            if periodo_vigente and mes_en_temporada_declarada(periodo_vigente, respuestas_diagnostico):
                hipotesis.append(Hipotesis(
                    kpi_id=kpi_id,
                    causa_probable=(
                        f"el período vigente ({periodo_vigente}) cae en la época que la clínica "
                        "declaró como complicada (P51) — puede ser estacionalidad, no un problema estructural"
                    ),
                    confianza="media",
                    preguntas_que_la_sustentan=["P51"],
                ))

        diagnosticos.append(Diagnostico(
            kpi_id=kpi_id,
            problema=KPI_BY_ID[kpi_id].nombre,
            estado=estado,
            hechos=[f"valor_actual={info.get('valor')}", f"direccion={gap.direccion}"],
            anomalias=anomalias,
            hipotesis=hipotesis,
            contradicciones=contradicciones_kpi,
            patrones_cruzados=patrones_kpi,
            informacion_faltante=informacion_faltante,
            confianza=suficiencia if suficiencia is not None else 1.0,
        ))

    return diagnosticos
