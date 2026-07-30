"""
coverage.py

Dado un set de variables ya normalizadas (por migración y/o wizard),
determina:
  - qué KPIs se pueden calcular ya mismo (con qué valor y confianza)
  - qué KPIs quedan parciales, y cuál es la ÚNICA variable que falta
  - la lista deduplicada de variables pendientes para mandar al wizard
    (una variable compartida por 3 KPIs aparece una sola vez)

Este es el reemplazo del chequeo "por KPI completo" que se había diagramado
al principio: acá se chequea variable por variable, así el wizard nunca
repite una pregunta que ya se puede inferir de otra parte del embudo.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from agregados import calcular_agregado
from reconciliacion import FUENTE_DERIVADA
from schema import KPI_FORMULAS, INTERNAL_VARIABLES, SOLO_MIGRACION_O_SISTEMA, VARIABLE_TYPES
from preguntas_wizard import obtener_pregunta
from trazabilidad import Trazabilidad, explicar


def _inferir_metodo(fuente: str) -> str:
    """Fase D1: de dónde salió el NÚMERO en sí — no el archivo, el
    número — más allá de por qué `fuente` llegó. "medido" (una celda
    real de una migración), "estimado" (el dueño contestó de memoria en
    el wizard — las preguntas de preguntas_wizard.py dicen
    "aproximadamente" a propósito) o "derivado" (despejado
    algebraicamente de una tasa declarada, ver derivacion.py).

    Se infiere de `fuente`, que ya existe en cada VariableValue — ningún
    extractor, ni el wizard, ni derivacion.py necesitan cambiar para
    poblar esto (ver `VariableValue.__post_init__`)."""
    if fuente == FUENTE_DERIVADA:
        return "derivado"
    if fuente == "wizard":
        return "estimado"
    return "medido"


@dataclass
class VariableValue:
    valor: Any
    fuente: str            # "migracion_excel" | "migracion_foto" | "wizard" | "sistema" | "confirmado_por_dueno"
    confianza: float = 1.0  # 0-1. Baja confianza => se muestra como sugerencia a confirmar, no se da por hecho.
    archivo_origen: Optional[str] = None  # nombre de archivo, o "wizard"/"sistema" si no viene de un archivo
    # Dimensión de período (plan de confiabilidad, hallazgo 1.1 y 4): si la
    # fuente traía una columna de período, `serie` guarda {período: valor}
    # de TODOS los períodos reales (la fila TOTAL/Promedio ya se excluyó en
    # el extractor). `valor` siempre es el período VIGENTE (el más
    # reciente de `serie`) — nunca un promedio de todo el rango — así las
    # 20 fórmulas de schema.py, que solo conocen `.valor`, no se tocan.
    serie: Optional[dict[str, Any]] = None
    periodo: Optional[str] = None  # etiqueta del período que representa `valor` (ej. "Abril 2026")
    # Fase 1 (normalización de períodos): `serie` usa claves canónicas
    # ("2026-04") para que dos archivos que etiquetan el mismo mes distinto
    # sí intersecten en coverage._calcular_serie_kpi — ver periodos.py.
    # `etiquetas_originales` guarda {clave_canonica: etiqueta_cruda} para
    # poder mostrar "Abril 2026" en vez de "2026-04" sin perder la clave
    # que hace funcionar la intersección.
    etiquetas_originales: Optional[dict[str, str]] = None
    # Filas de la hoja cuya etiqueta de período NO resuelve a clave canónica
    # ({etiqueta_cruda: valor}) — típicamente notas al pie o filas TOTAL que
    # el modelo no listó en `filas_excluidas`. No entran a `serie` (no son un
    # período, y elegirlas como valor vigente producía throughput = 0), pero
    # quedan acá para poder auditarlas: mismo principio que
    # `variables_en_cuarentena`, nada desaparece en silencio.
    periodos_no_reconocidos: Optional[dict[str, Any]] = None
    # Fase 0 del plan de evolución (lineage): de qué celda(s) salió el
    # valor, qué agregación y conversión de unidad se aplicaron. Default
    # None a propósito — variables de wizard, sistema, o extractores que
    # todavía no la pueblan (vision_parser) siguen funcionando igual.
    trazabilidad: Optional[Trazabilidad] = None
    # Fase D1: "medido" | "estimado" | "derivado" — ver _inferir_metodo.
    # None (default) se resuelve solo en __post_init__ a partir de
    # `fuente`, así ningún call-site existente (excel_parser.py,
    # derivacion.py, el wizard, etc.) necesita cambiar para poblarlo. Se
    # puede pasar explícito si algún día hace falta un caso que la
    # inferencia automática no cubra bien.
    metodo: Optional[str] = None  # "medido" | "estimado" | "derivado"

    def __post_init__(self):
        if self.metodo is None:
            self.metodo = _inferir_metodo(self.fuente)


@dataclass
class Conflicto:
    variable: str
    candidatos: list[dict] = field(default_factory=list)  # [{"valor", "archivo", "fuente", "confianza"}]
    # Fase E: distingue un desacuerdo real (dos fuentes que SÍ hablan del
    # mismo período y dan números distintos) de una comparación entre
    # fuentes con cobertura temporal distinta (una trae serie con fecha,
    # la otra sólo un escalar sin fecha — pueden estar hablando de meses
    # diferentes, no necesariamente en conflicto). Sigue bloqueando en
    # ambos casos — lo único que cambia es la pregunta que se le hace al
    # dueño de la clínica (ver pipeline.py). Default preserva el
    # comportamiento de siempre para todo conflicto ya existente.
    tipo: str = "valores_distintos"  # | "cobertura_distinta"


@dataclass
class CoverageResult:
    kpis_calculados: dict[int, dict] = field(default_factory=dict)
    kpis_parciales: dict[int, list[str]] = field(default_factory=dict)   # id -> variables que faltan
    kpis_bloqueados_por_diseno: list[int] = field(default_factory=list)  # variables internas, no se piden nunca
    kpis_esperando_facturas: list[int] = field(default_factory=list)     # variables financieras, solo migración
    kpis_esperando_resolucion_conflicto: dict[int, list[str]] = field(default_factory=dict)  # id -> variables en conflicto
    kpis_con_error: dict[int, str] = field(default_factory=dict)         # id -> motivo (nunca se traga en silencio)
    variables_pendientes: list[str] = field(default_factory=list)        # deduplicadas, listas para el wizard
    variables_baja_confianza: list[str] = field(default_factory=list)    # para confirmar, no repreguntar desde cero


def _calcular_serie_kpi(kpi, variables: dict[str, VariableValue], requeridas: list[str]) -> Optional[dict]:
    """
    Si TODAS las variables que requiere el KPI traen serie histórica, arma
    la serie del KPI aplicando la misma fórmula en cada período común —
    esto es lo que le permite al agente de interpretación (Fase 4) razonar
    sobre tendencia ("pasaste de X a Y") en vez de un solo número aislado
    (hallazgo 4 del informe de deficiencias).
    """
    series = {k: variables[k].serie for k in requeridas}
    if not all(series.values()):
        return None
    periodos_comunes = set.intersection(*(set(s.keys()) for s in series.values()))
    if not periodos_comunes:
        return None
    # Orden cronológico: se toma del orden de la serie de la primera
    # variable (ya viene en orden de aparición, no alfabético — ver
    # excel_parser._construir_serie_periodo).
    orden = [p for p in next(iter(series.values())) if p in periodos_comunes]
    resultado = {}
    for periodo in orden:
        payload = {k: series[k][periodo] for k in requeridas}
        try:
            valor = kpi.calcular(payload)
        except Exception:
            continue
        # Un KPI porcentual (_pct en schema.py) devuelve None, no una
        # excepción, cuando el denominador de ESE período fue 0 (ej. un
        # mes sin turnos agendados) — no lo guarda como "el valor de ese
        # período es None": lo salta, igual que un período que tira
        # excepción. Guardar None colaba un valor no numérico en la serie
        # (bug real: agregados.calcular_agregado(..., "ultimo") explotaba
        # si ese período resultaba ser el más reciente).
        if valor is not None:
            resultado[periodo] = valor
    return resultado or None


def evaluar_cobertura(
    variables: dict[str, VariableValue],
    variables_en_conflicto: Optional[set[str]] = None,
) -> CoverageResult:
    resultado = CoverageResult()
    pendientes_set: set[str] = set()
    variables_en_conflicto = variables_en_conflicto or set()

    for kpi in KPI_FORMULAS:
        requeridas = kpi.variables
        faltantes = [v for v in requeridas if v not in variables]
        internas_faltantes = [v for v in faltantes if v in INTERNAL_VARIABLES]
        conflicto_faltantes = [v for v in faltantes if v in variables_en_conflicto]
        financieras_faltantes = [v for v in faltantes if v in SOLO_MIGRACION_O_SISTEMA]

        if internas_faltantes:
            # Estas nunca se preguntan al dueño de la clínica: las calcula
            # el propio sistema (comparación histórica, conteo interno).
            resultado.kpis_bloqueados_por_diseno.append(kpi.id)
            continue

        if conflicto_faltantes:
            # Hay valores distintos sin resolver para alguna variable que
            # este KPI necesita: no se calcula ni se pregunta como si fuera
            # nueva — se muestra como conflicto a resolver (ver conflictos.py).
            resultado.kpis_esperando_resolucion_conflicto[kpi.id] = conflicto_faltantes
            continue

        if financieras_faltantes:
            # Estas tampoco se preguntan — dependen de facturas migradas o
            # de la integración con el sistema de cobros/agenda. El KPI
            # queda visible como "esperando facturas", no como pregunta.
            resultado.kpis_esperando_facturas.append(kpi.id)
            continue

        if faltantes:
            resultado.kpis_parciales[kpi.id] = faltantes
            pendientes_set.update(faltantes)
            continue

        payload = {k: variables[k].valor for k in requeridas}
        try:
            valor = kpi.calcular(payload)
        except Exception as e:
            # Un valor con forma inesperada (ej. un extractor que guardó un
            # escalar donde la fórmula espera un dict) no debe tirar abajo
            # toda la migración — pero tampoco puede desaparecer en
            # silencio: queda registrado en kpis_con_error para que se
            # pueda auditar qué pasó, en vez de que el KPI simplemente no
            # aparezca sin explicación (deuda que dejó el fix original de
            # este try/except — ver plan de confiabilidad del agente).
            resultado.kpis_con_error[kpi.id] = f"{type(e).__name__}: {e}"
            continue
        confianza_min = min(variables[k].confianza for k in requeridas)
        serie_kpi = _calcular_serie_kpi(kpi, variables, requeridas)

        resultado.kpis_calculados[kpi.id] = {
            "nombre": kpi.nombre,
            "valor": valor,
            "unidad": kpi.unidad,
            "confianza": confianza_min,
            "fuentes": sorted({variables[k].fuente for k in requeridas}),
            "serie": serie_kpi,
            # Fase 1: agregados sobre la serie histórica, al lado de
            # `valor` — que sigue siendo el último período real (decisión
            # 2 del plan: no se reintroduce la ambigüedad que cerró el
            # hallazgo 1.1, el promedio nunca reemplaza al vigente).
            "agregados": {
                "promedio": calcular_agregado(serie_kpi, "promedio"),
                "mediana": calcular_agregado(serie_kpi, "mediana"),
                "ultimo": calcular_agregado(serie_kpi, "ultimo"),
            } if serie_kpi else None,
            # Fase 0 (lineage): de dónde salió cada variable que compone
            # este KPI — ver trazabilidad.explicar() para el texto legible.
            "trazabilidad": {k: variables[k].trazabilidad for k in requeridas},
            "trazabilidad_legible": {k: explicar(variables[k]) for k in requeridas},
        }
        if confianza_min < 0.7:
            resultado.variables_baja_confianza.extend(
                k for k in requeridas if variables[k].confianza < 0.7
            )

    resultado.variables_pendientes = sorted(pendientes_set)
    resultado.variables_baja_confianza = sorted(set(resultado.variables_baja_confianza))
    return resultado


def variables_para_wizard(resultado: CoverageResult) -> list[dict]:
    """
    Arma la lista de preguntas que el wizard debe mostrar, con contexto de
    qué KPIs desbloquea cada una — esto es lo que le permite al wizard
    priorizar (ej. mostrar primero las variables que desbloquean más KPIs).
    """
    impacto: dict[str, list[int]] = {}
    for kpi_id, faltantes in resultado.kpis_parciales.items():
        for var in faltantes:
            impacto.setdefault(var, []).append(kpi_id)

    preguntas = []
    for var, kpis in impacto.items():
        pregunta = obtener_pregunta(var)
        preguntas.append({
            "variable": var,
            "tipo": VARIABLE_TYPES.get(var, "text"),
            "pregunta": pregunta.pregunta if pregunta else f"(falta definir pregunta para {var})",
            "referencia_guia": pregunta.referencia_guia if pregunta else None,
            "adaptada_de_la_guia": pregunta.adaptada if pregunta else None,
            "kpis_que_desbloquea": sorted(kpis),
            "prioridad": len(kpis),  # más KPIs desbloqueados = se pregunta antes
        })
    return sorted(preguntas, key=lambda p: -p["prioridad"])
