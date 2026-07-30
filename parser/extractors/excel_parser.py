"""
extractors/excel_parser.py

Un Excel de una clínica real casi nunca tiene columnas prolijas, ni una
sola hoja útil, ni el encabezado en la fila 0. Puede decir "Monto",
"Importe", "Total", o "$" para lo mismo; puede tener 3 hojas con datos
distintos (embudo, financiero, operativo); puede tener una fila de título
y una fila en blanco antes del encabezado real. Este módulo no intenta
adivinar con reglas fijas porque se rompe con la primera clínica que arme
su planilla distinto. En cambio:

  1. pandas lee cada hoja del archivo en crudo (sin asumir dónde está el
     encabezado) y arma una vista previa de sus primeras filas.
  2. Claude ve esa vista cruda de todas las hojas y devuelve, por hoja, la
     ORIENTACIÓN de la tabla, cuál fila es el encabezado real, y el mapeo
     semántico de cada columna/fila (por posición, no por nombre) contra
     el diccionario de métricas de schema.py.
  3. Con eso identificado, se vuelve a leer cada hoja bien formada y se
     aplica el mapeo: se agregan/normalizan los valores y, cuando hay una
     columna de período, se arma además la serie histórica.

Contrato v2 (plan de confiabilidad del agente de diagnóstico, hallazgos
1.1/1.3/C): a diferencia de la v1, que solo clasificaba columnas y
promediaba a ciegas, esta versión:
  - distingue "orientacion" de la hoja (períodos en filas / una fila por
    métrica distinta / transaccional) — evita que una hoja "una fila =
    una métrica" (ej. tiempo de respuesta + horas manuales + % automatizado
    todo en la misma columna "Valor") se trate como si fuera una sola
    serie y se promedien entre sí métricas sin relación.
  - excluye explícitamente filas de TOTAL/Promedio antes de agregar nada
    (el bug real: una fila "TOTAL / Prom." se estaba promediando como si
    fuera un mes más, inflando cada número ~71%).
  - arma una serie histórica por período cuando hay una columna de
    período, y usa el ÚLTIMO período real como "valor vigente" — nunca
    un promedio que mezcla todo el rango con la fila total.
  - declara la unidad de origen de cada columna y el código aplica la
    conversión (el modelo nunca hace la aritmética de conversión él
    mismo, que es donde fallaba: "6.5 horas" quedaba guardado como "6.5
    min" en vez de 390).

El resultado son VariableValue con fuente="migracion_excel" (o
"migracion_excel:<hoja>" cuando el archivo tiene más de una hoja) y una
confianza que baja si Claude no está seguro del mapeo de una columna.
"""

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

import pandas as pd

from schema import KPI_FORMULAS, METRICAS, METRICAS_EXTRAIBLES, VARIABLE_TYPES
from coverage import VariableValue
from claude_utils import extraer_texto
from trazabilidad import Trazabilidad
from matching import RegistroClientes, encontrar_o_crear_cliente
from ledger import TIPOS_EVENTO, construir_ledger_pacientes
import periodos

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


MODEL = "claude-sonnet-5"
FILAS_PREVIEW = 10


@dataclass
class TasaDeclarada:
    """Una tasa/porcentaje que la propia planilla ya trae calculada.

    Siempre en porcentaje 0-100 (la unidad en la que trabajan las fórmulas
    de schema.py), sin importar si la hoja la guardaba como fracción.
    `serie` es {período: %} cuando la hoja tiene eje temporal.
    """
    vigente: float
    serie: Optional[dict[str, float]] = None

# excel_parser nunca intenta mapear variables tipo "list" (ej.
# tareas_sin_backup: [{tarea, responsable}, ...]) — una planilla rara vez
# trae esa estructura, y forzarla producía el hallazgo B (un conteo suelto
# como "4" terminaba guardado donde se esperaba una lista de tareas). Esas
# variables se piden en el wizard, no se extraen de Excel.
#
# Tampoco "ledger" (ledger_pacientes) por MAPEO columna-a-columna: a
# diferencia de las demás variables, un ledger necesita varias columnas a
# la vez (nombre + fecha + tipo + monto + tratamiento) resueltas contra
# matching.py — no encaja en "una columna, una variable, un valor". Fase
# H4b: el modelo SÍ lo declara a través del prompt, pero en un bloque
# aparte ("ledger", ver más abajo), no como una entrada más de "mapeo";
# `construir_ledger_pacientes` en ledger.py sigue siendo quien arma el
# resultado final a partir de los registros ya planos.
VARIABLES_EXCEL = {v: info for v, info in METRICAS_EXTRAIBLES.items() if VARIABLE_TYPES.get(v) not in ("list", "ledger")}
VARIABLES_DICT = sorted(v for v in VARIABLES_EXCEL if VARIABLE_TYPES.get(v) == "dict")

UNIDADES_DATO_USADAS = sorted({info.unidad_dato for info in VARIABLES_EXCEL.values()})

# El modelo solo DECLARA en qué unidad está el dato de origen; la
# conversión numérica la hace siempre el código (nunca el modelo — ahí
# fallaba antes: "convertí vos el valor a minutos" nunca se podía cumplir
# porque el contrato solo transportaba índices de columna + agregación).
FACTORES_CONVERSION: dict[tuple[str, str], float] = {
    ("horas", "minutos"): 60,
    ("minutos", "horas"): 1 / 60,
    ("dias", "minutos"): 24 * 60,
    ("dias", "horas"): 24,
}

# KPIs que son un % calculado a partir de un par de variables — reconciliacion.py
# (Fase 3) los usa para chequear cruzado si la hoja YA trae esa tasa
# calculada al lado del conteo crudo.
_KPIS_PORCENTUALES_JSON = json.dumps(
    [{"kpi_id": k.id, "nombre": k.nombre, "variables": k.variables} for k in KPI_FORMULAS if k.unidad == "%"],
    ensure_ascii=False, indent=2,
)

_VARIABLES_JSON = json.dumps(
    {v: {"nombre": info.nombre_humano, "definicion": info.definicion,
         "unidad_esperada": info.unidad_dato,
         "no_confundir_con": info.no_confundir_con or None}
     for v, info in VARIABLES_EXCEL.items()},
    ensure_ascii=False, indent=2,
)

# Fase H4b: vocabulario de tipo_evento para el bloque "ledger" de una hoja
# transaccional — se le pasa al modelo desde acá, sin duplicarlo.
_TIPOS_EVENTO_JSON = json.dumps(sorted(TIPOS_EVENTO), ensure_ascii=False)

SYSTEM_PROMPT = f"""Sos un normalizador de datos para clínicas dentales argentinas.
Te paso, por cada hoja de un Excel (o la única hoja implícita de un CSV),
una vista cruda de sus primeras {FILAS_PREVIEW} filas — SIN asumir dónde
está el encabezado: es común que haya una fila de título y una fila vacía
antes de la fila real de nombres de columna (reportes armados a mano).

IMPORTANTE: todos los índices de fila que uses en tu respuesta
("fila_encabezado", "filas_excluidas", "fila_index") se refieren a la
MISMA numeración 0-based del grid crudo que te paso — no a la tabla ya
"limpia". Los índices de columna también son 0-based sobre ese mismo grid.

Cuando el archivo es un Excel, cada hoja puede traer también
"formatos_columna": {{indice_de_columna: formato}} leído del propio
archivo. Usalo, es un dato duro, no una pista: una columna con formato
"porcentaje" es una TASA ya calculada — nunca la mapees a una variable de
conteo o de monto. Esa columna va en "tasas_declaradas" (punto 7), no en
"mapeo". Una columna "moneda" es un monto en pesos, no un conteo.

Tu trabajo, por cada hoja:

1. Identificar el índice de la fila que contiene los nombres de columna
   reales ("fila_encabezado"). Si la hoja no tiene una tabla reconocible,
   devolvé "fila_encabezado": null y "mapeo": [].

2. Clasificar la "orientacion" de la tabla — esto es crítico, un error acá
   arruina todo lo que sigue:
   - "periodos_en_filas": cada fila es un período (mes/semana) con varias
     métricas en columnas. Ej: una fila por mes, columnas "Consultas
     nuevas", "Turnos agendados", etc.
   - "metricas_en_filas": cada fila es una MÉTRICA DISTINTA, típicamente
     con columnas "Métrica"/"Valor" (a veces "Unidad", "Comentario"). Ojo:
     acá las filas NO son períodos de una misma variable, cada una es una
     variable distinta — nunca se agregan/promedian entre sí.
   - "transaccional": cada fila es un registro individual (una consulta,
     un presupuesto, un turno) sin agregación previa.

3. Si "orientacion" es "periodos_en_filas": indicá "columna_periodo" —
   el ÍNDICE numérico 0-based de la columna con el nombre del período
   (ej. 0), IGUAL que "columna_index" en el mapeo. NUNCA el nombre de la
   columna ni el texto de un período — un índice, como en todos los demás
   campos "*_index" de este contrato. Indicá también "filas_excluidas"
   — filas que NO son un período real: cualquier fila de TOTAL, Promedio,
   Prom., Acumulado, Subtotal, o cualquier fila cuyo valor sea la suma de
   las filas anteriores en esa columna. Estas filas son muy comunes en
   reportes armados a mano y NUNCA deben tratarse como un período más — si
   las incluís en un promedio, el número final queda inflado.

   Si "orientacion" es "transaccional" y la hoja trae una columna de FECHA
   por registro (no una etiqueta de mes, una fecha real de cada fila),
   **es OBLIGATORIO indicar esa columna en "columna_periodo"** — no es
   opcional cuando existe. El código arma con eso una serie histórica
   agrupando los registros por mes, igual que en periodos_en_filas.

   La consecuencia de omitirla cuando la columna existe: sin
   "columna_periodo", el código suma o agrega TODAS las filas de TODOS
   los meses juntas en un solo número — un archivo con 26 meses de
   historial termina reportado como si fuera el valor de un único
   período, que no corresponde a nada real y después no coincide con lo
   que declara otro archivo del mismo mes (genera un conflicto que en
   realidad no es tal, sólo falta la fecha). Ejemplo: una hoja de cobros
   con columna "fecha_hora" (formato "2024-08-03 09:30:00" o similar) —
   ESO es una columna de fecha por registro, declarala en
   "columna_periodo" aunque incluya hora además de la fecha.

   Sólo se omite "columna_periodo" cuando la hoja genuinamente NO tiene
   ninguna columna de fecha por fila (ej. un export sin timestamp) — ahí
   sí el sistema agrega el total, porque no hay otra opción.

   Además, revisá las filas ANTES del encabezado (título, subtítulo, notas
   sueltas) buscando una advertencia de que los números de ESA HOJA son
   estimados, se anotan a mano, o no salen de un sistema — por ejemplo
   "Estos numeros los estimo la recepcionista, no hay sistema". Si
   encontrás una nota así, marcá "hoja_estimada": true para toda la hoja
   (no por celda ni por variable — es una propiedad de la hoja entera).
   No confundas con un simple título de sección: tiene que haber una
   afirmación sobre CÓMO se produjo el dato, no sólo el nombre de la hoja.

   Si "orientacion" es "transaccional" y cada fila representa algo que le
   pasó a un paciente puntual (un turno, un cobro, un presupuesto, un
   tratamiento), además del "mapeo" normal (o incluso SIN mapeo si ninguna
   columna es un total agregable) declará un bloque "ledger" con esta
   forma:

   {{"columna_paciente_index": 1, "id_estable": true,
     "columna_fecha_index": 2,
     "eventos": [
       {{"tipo_evento": "pago", "columna_monto_index": 3,
         "columna_tratamiento_index": 5, "confianza": 0.8}}
     ]}}

   - "columna_paciente_index": la columna que identifica al paciente en
     CADA fila. "id_estable": true si es un código ya único (ej. "P1045"),
     false si es un nombre tipeado a mano (el código junta identidades
     parecidas con más cuidado en ese caso).
   - "columna_fecha_index": la fecha de cada registro (no una etiqueta de
     mes — la fecha real del evento).
   - "eventos": una fila de la hoja puede generar MÁS DE UN evento — por
     ejemplo, un presupuesto con estado "aceptado" es a la vez un
     "presupuesto_emitido" (siempre) Y un "presupuesto_aceptado" (solo esa
     fila). Para eso, cada entrada de "eventos" puede traer su propia
     "condicion" (misma sintaxis que en "mapeo": nombre real de columna,
     con backticks si tiene espacios) — sin "condicion", el evento se
     genera para TODAS las filas de la hoja. "tipo_evento" tiene que ser
     uno de: {_TIPOS_EVENTO_JSON}. "columna_monto_index" y
     "columna_tratamiento_index" son opcionales.
   - Si la hoja no tiene identidad de paciente por fila, no declares
     "ledger" — no inventes una columna que no está.

4. Mapear cada variable a UNA columna (para periodos_en_filas y
   transaccional) o a UNA fila+columna (para metricas_en_filas), del
   diccionario de variables de abajo. Cada una trae su definición completa,
   la unidad en la que se espera el dato, y con qué variable parecida NO
   hay que confundirla — usalo, ahí es donde más se equivocaba una versión
   anterior de este sistema:

{_VARIABLES_JSON}

   Las variables de este subconjunto son un desglose por categoría, no un
   número suelto (ej. horas por tarea, ingreso por tipo de tratamiento):

{json.dumps(VARIABLES_DICT, ensure_ascii=False, indent=2)}

   Para esas, indicá también "columna_categoria_index": la columna que da
   la categoría por la que agrupar. Si la hoja solo da un total ya
   agregado sin columna de categoría, mapeá igual sin
   "columna_categoria_index" — se guarda como desglose de una sola clave
   ("total").

5. Para cada regla de mapeo, declará "unidad_origen": la unidad en la que
   está el dato EN LA HOJA (no la que se espera). Unidades válidas:
   {json.dumps(UNIDADES_DATO_USADAS, ensure_ascii=False)}, más "horas",
   "minutos", "dias" si la hoja usa esas para algo que se espera en otra
   unidad. NO conviertas el número vos mismo — el código hace la
   conversión a partir de lo que declares acá. Si no sabés la unidad,
   usá la misma que "unidad_esperada" de la variable.

6. Para "metricas_en_filas": usá "fila_index" (índice de fila, misma
   numeración del grid crudo) en vez de "condicion" para elegir la fila
   que corresponde a cada variable, y "columna_index" para la columna del
   valor. No hace falta "agregacion" en este caso (se toma el valor de esa
   celda).

7. Chequeo cruzado — MUY IMPORTANTE, es la principal defensa contra
   mapear la columna equivocada: si la hoja también trae, al lado de los
   conteos crudos, una columna con una TASA o PORCENTAJE YA CALCULADO que
   corresponde a uno de estos KPIs, reportalo aparte en
   "tasas_declaradas" (no reemplaza el mapeo de variables, es redundante
   a propósito):

{_KPIS_PORCENTUALES_JSON}

   Por cada una que encuentres: {{"kpi_id": 4, "columna_index": 8,
   "unidad_origen": "fraccion|porcentaje"}} — "fraccion" si la hoja la
   guarda como 0-1 (ej. 0.22), "porcentaje" si ya está en 0-100 (ej. 22).
   Esto es lo que permite detectar después si, por ejemplo, "no_shows" se
   mapeó de la columna equivocada: si el conteo que se mapeó implica una
   tasa muy distinta a la que la propia hoja declara, algo está mal.

Reglas generales:
- Una columna de fecha de turno + estado ("asistió"/"no show") normalmente
  te da tanto "turnos_agendados" (conteo de filas) como "no_shows" (conteo
  de filas con estado ausente) — indicalo como dos reglas, con "condicion"
  referenciando el nombre real de columna (el texto de la fila de
  encabezado, no el índice).
- Lo mismo aplica a montos: si una hoja transaccional trae presupuestos con
  una columna de estado ("aceptado"/"pendiente"/"rechazado"), la suma total
  de la columna de monto NO es lo mismo que la suma de los aceptados —
  son dos variables distintas ("monto_presupuestos_emitidos" vs.
  "monto_presupuestos_aceptados"). Para la segunda, sumá SOLO las filas con
  el estado correspondiente usando "condicion" con "agregacion": "sum", por
  ejemplo {{"variable": "monto_presupuestos_aceptados", "agregacion": "sum",
  "condicion": "estado == 'aceptado'"}}. Nunca reportes el total sin
  filtrar como si fuera el aceptado.
- La "condicion" tiene que ser una expresión de pandas.query() válida sobre
  el nombre REAL de columna (el texto de la fila de encabezado, no el
  índice): si ese nombre tiene espacios o puntos (ej. "Estado turno",
  "Presup. entregados"), envolvelo en backticks — `Estado turno` ==
  'aceptado' — si no, la condición no se puede evaluar y la regla entera
  se descarta.
- Si una columna es ambigua entre dos variables, elegí la más probable
  según el contexto de las otras columnas y bajá la confianza a 0.5 o menos.
- Nunca inventes una variable que no está en la lista de arriba.
- Devolvé SOLO JSON, sin texto adicional, con este formato exacto:

{{
  "hojas": [
    {{
      "hoja": "nombre de la hoja tal cual te la pasé (o null si es un CSV)",
      "fila_encabezado": 0,
      "orientacion": "periodos_en_filas | metricas_en_filas | transaccional",
      "columna_periodo": "opcional, solo si orientacion es periodos_en_filas",
      "filas_excluidas": [8],
      "hoja_estimada": "opcional (default false), true solo si hay una nota explícita",
      "mapeo": [
        {{"columna_index": 1, "fila_index": null, "variable": "...",
          "agregacion": "sum|count|count_where|avg",
          "condicion": "opcional, ej. estado == 'no show'",
          "columna_categoria_index": "opcional, solo para variables tipo dict",
          "unidad_origen": "...", "confianza": 0.0-1.0}}
      ],
      "ledger": "opcional, solo si orientacion es transaccional y hay identidad de paciente por fila — ver más arriba",
      "tasas_declaradas": [
        {{"kpi_id": 4, "columna_index": 8, "unidad_origen": "fraccion|porcentaje"}}
      ],
      "columnas_sin_mapeo": [1, 3]
    }}
  ]
}}
"""


def _grid_serializable(df: pd.DataFrame) -> list[list]:
    return df.where(pd.notnull(df), None).values.tolist()


def leer_hojas_crudas(path: str) -> list[dict]:
    """Vista previa cruda (sin asumir encabezado) de cada hoja del archivo."""
    if path.endswith(".csv"):
        df = pd.read_csv(path, header=None, nrows=FILAS_PREVIEW)
        return [{"hoja": None, "grid": _grid_serializable(df)}]

    hojas = []
    excel = pd.ExcelFile(path)
    formatos = leer_formatos_columna(path)
    for nombre in excel.sheet_names:
        df = excel.parse(nombre, header=None, nrows=FILAS_PREVIEW)
        hoja = {"hoja": nombre, "grid": _grid_serializable(df)}
        if nombre in formatos:
            hoja["formatos_columna"] = formatos[nombre]
        hojas.append(hoja)
    return hojas


def _clasificar_formato(number_format: str) -> str:
    """Traduce un formato de celda de Excel a una etiqueta semántica.

    El formato es una señal DETERMINISTA que hasta ahora se tiraba: una
    celda formateada `0.00%` es por definición una tasa, no un conteo —
    exactamente la confusión que originó el bug de `no_shows`. No depende
    de que el modelo acierte.
    """
    if not number_format:
        return "general"
    fmt = number_format.lower()
    if "%" in fmt:
        return "porcentaje"
    # El símbolo de moneda en Excel puede venir escapado ("\$") o como
    # código de moneda entre corchetes ([$ARS]).
    if "$" in fmt or "€" in fmt or "[$" in fmt:
        return "moneda"
    if any(t in fmt for t in ("yy", "mmm", "dd/", "hh:")):
        return "fecha"
    if fmt in ("general", "@"):
        return "general" if fmt == "general" else "texto"
    if "0" in fmt or "#" in fmt:
        return "decimal" if "." in fmt else "entero"
    return "general"


def leer_formatos_columna(path: str, filas_muestra: int = 30) -> dict[str, dict[int, str]]:
    """
    {hoja: {indice_columna_0based: etiqueta_de_formato}} usando openpyxl.

    Se queda con el formato DOMINANTE de las celdas con dato de cada
    columna (una fila de encabezado suele tener formato distinto al de los
    datos, así que la mayoría es más confiable que mirar una sola celda).
    Un CSV no tiene formatos: devuelve {} y todo el resto sigue igual.
    """
    if not path.endswith((".xlsx", ".xlsm", ".xltx")):
        return {}  # CSV y .xls antiguo: sin metadata de formato disponible

    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return {}  # nunca romper la extracción por no poder leer formatos

    resultado: dict[str, dict[int, str]] = {}
    try:
        for ws in wb.worksheets:
            conteo: dict[int, dict[str, int]] = {}
            for fila in ws.iter_rows(min_row=1, max_row=filas_muestra):
                for celda in fila:
                    if celda.value is None or isinstance(celda.value, str):
                        continue  # el encabezado y las notas no describen el formato de los datos
                    etiqueta = _clasificar_formato(celda.number_format)
                    conteo.setdefault(celda.column - 1, {}).setdefault(etiqueta, 0)
                    conteo[celda.column - 1][etiqueta] += 1
            dominante = {
                idx: max(etiquetas.items(), key=lambda kv: kv[1])[0]
                for idx, etiquetas in conteo.items() if etiquetas
            }
            if dominante:
                resultado[ws.title] = dominante
    finally:
        wb.close()

    return resultado


def pedir_mapeo_a_claude(hojas_crudas: list[dict], client) -> dict:
    respuesta = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": json.dumps({"hojas": hojas_crudas}, ensure_ascii=False, default=str),
        }],
    )
    texto = extraer_texto(respuesta).strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1].removeprefix("json").strip()
    return json.loads(texto)


def _releer_con_encabezado(path: str, hoja: Optional[str], fila_encabezado: int) -> pd.DataFrame:
    if path.endswith(".csv"):
        return pd.read_csv(path, header=fila_encabezado)
    return pd.read_excel(path, sheet_name=hoja, header=fila_encabezado)


def _a_entero(valor: Any) -> Optional[int]:
    """Coerción defensiva de cualquier campo "*_index" que Claude debía
    devolver como índice numérico. Un LLM ocasionalmente devuelve el
    nombre de la columna en vez del índice (visto en la práctica con
    "columna_periodo") — en vez de que eso reviente más abajo con un
    TypeError al comparar str con int, se descarta la regla puntual
    (devuelve None) en lugar de adivinar a qué columna se refería."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, str) and valor.strip().lstrip("-").isdigit():
        return int(valor)
    return None


def _a_indice_relativo(fila_encabezado: int, fila_raw: Optional[int]) -> Optional[int]:
    """Convierte un índice de fila del grid crudo (lo que reporta Claude)
    al índice 0-based que tiene esa misma fila en el DataFrame ya leído
    con `header=fila_encabezado` (que pandas re-indexa a partir de 0)."""
    fila_raw = _a_entero(fila_raw)
    if fila_raw is None:
        return None
    relativo = fila_raw - fila_encabezado - 1
    return relativo if relativo >= 0 else None


def _factor_de_conversion(var: str, unidad_origen: Optional[str]) -> Optional[float]:
    """Factor que `_convertir_unidad` aplicaría, sin aplicarlo — separado
    para que `aplicar_mapeo` pueda registrar el mismo factor en la
    Trazabilidad sin duplicar la lógica de qué conversión corresponde."""
    info = METRICAS.get(var)
    if info is None or not unidad_origen or unidad_origen == info.unidad_dato:
        return None
    return FACTORES_CONVERSION.get((unidad_origen, info.unidad_dato))


def _convertir_unidad(var: str, valor: Any, unidad_origen: Optional[str]) -> Any:
    factor = _factor_de_conversion(var, unidad_origen)
    if factor is None:
        return valor  # sin conversión declarada, o unidad no reconocida: no se inventa una
    if isinstance(valor, dict):
        return {k: round(v * factor, 4) if isinstance(v, (int, float)) else v for k, v in valor.items()}
    if isinstance(valor, (int, float)):
        return round(valor * factor, 4)
    return valor


def _agregar_escalar(serie: pd.Series, agregacion: str) -> Optional[float]:
    if agregacion == "sum":
        return float(pd.to_numeric(serie, errors="coerce").sum())
    if agregacion == "count":
        return int(serie.count())
    if agregacion == "count_where":
        return int(len(serie))
    if agregacion == "avg":
        return float(pd.to_numeric(serie, errors="coerce").mean())
    return None


def _agregar_dict(
    df_filtrado: pd.DataFrame,
    col_valor: str,
    idx_categoria: Optional[int],
    columnas_originales: pd.Index,
    agregacion: str,
    resolver_categoria: Optional[Callable[[str], str]] = None,
) -> Optional[dict]:
    """Arma el desglose {categoria: valor} para una variable tipo dict.

    Si no hay columna de categoría (la hoja solo da un total ya agregado),
    se devuelve un desglose de una sola clave "total" en vez de un escalar
    suelto — así el valor sigue siendo compatible con lo que esperan las
    fórmulas de schema.py (que siempre iteran sobre .values()).

    `resolver_categoria` (Fase 2, ledger de pacientes): si se pasa, cada
    valor de la columna categoría pasa por esta función ANTES de agrupar
    — es el gancho de matching.py para `ingreso_por_paciente`: "Juan
    Pérez" y "J. Perez" se resuelven al mismo ID antes del groupby, en vez
    de sumar por separado y subestimar el LTV en silencio. None (default)
    conserva el comportamiento de siempre: la categoría cruda tal cual.
    """
    valores = pd.to_numeric(df_filtrado[col_valor], errors="coerce")

    if idx_categoria is None or idx_categoria >= len(columnas_originales):
        total = valores.mean() if agregacion == "avg" else valores.sum()
        if pd.isna(total):
            return None
        return {"total": round(float(total), 2)}

    col_categoria = columnas_originales[idx_categoria]
    if col_categoria not in df_filtrado.columns or col_categoria == col_valor:
        return None

    categorias = df_filtrado[col_categoria].astype(str).str.strip()
    if resolver_categoria is not None:
        categorias = categorias.map(resolver_categoria)
    agrupado = valores.groupby(categorias)
    if agregacion == "avg":
        resultado = agrupado.mean()
    elif agregacion in ("count", "count_where"):
        resultado = agrupado.count()
    else:
        resultado = agrupado.sum()

    resultado = resultado.dropna()
    desglose = {
        str(k): round(float(v), 2)
        for k, v in resultado.items()
        if str(k) and str(k).lower() != "nan"
    }
    return desglose or None


def _construir_serie_periodo(
    df_filtrado: pd.DataFrame, col_valor: str, col_periodo: str, agregacion: str,
) -> tuple[Optional[dict], dict[str, str], dict[str, float]]:
    """{período_canónico: valor} para una variable escalar en una hoja con
    columna de período.

    Dos guardas contra filas que no son un período (bug real, encontrado
    con una planilla de clínica: la hoja "Financiero" tenía una nota al
    pie — "Presupuestado = presup. entregados x ticket..." — que se colaba
    como período y terminaba siendo el VALOR VIGENTE de `monto_cobrado`,
    o sea throughput = 0):

    1. `min_count=1` en la suma. Sin eso, `groupby().sum()` de un grupo
       enteramente NaN devuelve 0.0 — un cero fabricado que `dropna()` no
       filtra porque es un número perfectamente válido. Con min_count=1
       devuelve NaN y desaparece. Esto sólo cubre la fila basura SIN dato
       numérico en esta columna.
    2. `periodos.es_canonico`: una etiqueta que no resuelve a clave
       canónica no entra a la serie. Cubre el otro caso — la fila basura
       CON dato numérico, típicamente un TOTAL que el modelo no listó en
       `filas_excluidas` (hallazgo 1.1). No se descarta en silencio: sale
       por el tercer elemento del retorno.

    No se puede confiar sólo en `filas_excluidas` para esto: lo llena el
    modelo, y el prompt le pide excluir TOTAL/Promedio/Subtotal — una nota
    al pie no es ninguna de esas cosas. La corrección no puede depender de
    que un LLM enumere exhaustivamente el ruido de cada planilla.

    Fase 1 del plan de evolución: la clave ya no es la etiqueta cruda de la
    hoja ("Abril 2026") sino la canónica que arma `periodos.normalizar_periodo`
    ("2026-04") — dos archivos que etiquetan el mismo mes distinto ahora
    intersectan en `coverage._calcular_serie_kpi`, cosa que antes fallaba
    en silencio (ver docstring del módulo `periodos.py`), y el orden final
    es cronológico por clave canónica (`orden_cronologico`) en vez de
    depender del orden de aparición de las filas en el archivo.

    Devuelve (serie, etiquetas_originales, no_reconocidos):
      - `etiquetas_originales` mapea cada clave canónica a la etiqueta cruda
        tal como venía en la hoja, para poder mostrarla sin perder la clave
        que hace intersectar series. Cuando varias filas caen en el mismo
        período (hoja transaccional, una fecha real por fila) se guarda la
        de fecha más temprana — sólo para mostrar, nunca afecta el cálculo.
      - `no_reconocidos` es {etiqueta_cruda: valor} de las filas rechazadas
        por la guarda 2. Queda visible para auditar — misma filosofía que
        `variables_en_cuarentena`: lo dudoso no desaparece en silencio.
        Si TODAS las etiquetas de la hoja son no canónicas (ej. una planilla
        rotulada "Semana 1".."Semana 5"), la serie queda vacía y el llamador
        cae al agregado escalar, que es exactamente lo que ya hace cuando la
        hoja no declara columna de período.

    Bug real (planilla real de clínica): agrupar por la etiqueta CRUDA y
    recién después normalizar a clave canónica hace que, en una hoja
    transaccional con una fecha por fila (ej. "2026-03-05", "2026-03-18",
    "2026-03-25"...), cada fecha sea su propio grupo — el `groupby` nunca
    ve que tres de esas fechas son "el mismo mes". Al normalizar, las tres
    colisionan en la misma clave y la última pisa a las anteriores: la serie
    terminaba con el valor del último día del mes, no la suma/promedio del
    mes entero (presupuestos aceptados de marzo: 787.000 en vez de
    8.989.000). Por eso acá se normaliza PRIMERO y se agrupa por la clave
    canónica — así el `groupby` agrega de verdad lo que corresponde al mismo
    período, con la `agregacion` declarada (sum suma el mes, avg lo
    promedia; acumular a mano en un loop rompería avg).
    """
    valores = pd.to_numeric(df_filtrado[col_valor], errors="coerce")
    periodos_crudos = df_filtrado[col_periodo].astype(str).str.strip()

    # Mismo filtro de siempre (celda de período vacía o literalmente "nan"
    # tras el astype(str)), sólo que ahora se aplica ANTES de agrupar en vez
    # de después — no cambia qué se descarta, sólo cuándo.
    validos = (periodos_crudos != "") & (periodos_crudos.str.lower() != "nan")
    valores = valores[validos]
    periodos_crudos = periodos_crudos[validos]

    claves = periodos_crudos.map(periodos.normalizar_periodo)
    es_periodo = claves.notna() & claves.map(periodos.es_canonico)

    serie: dict[str, float] = {}
    etiquetas_originales: dict[str, str] = {}
    no_reconocidos: dict[str, float] = {}

    if es_periodo.any():
        valores_periodo = valores[es_periodo]
        claves_periodo = claves[es_periodo]
        crudas_periodo = periodos_crudos[es_periodo]

        agrupado = valores_periodo.groupby(claves_periodo, sort=False)
        # min_count=1 (guarda 1): un grupo sin ningún valor numérico debe
        # dar NaN, no 0.0. `mean()` ya se comporta así por default.
        resultado = agrupado.mean() if agregacion == "avg" else agrupado.sum(min_count=1)
        resultado = resultado.dropna()
        for clave, valor in resultado.items():
            serie[clave] = round(float(valor), 4)

        # Etiqueta representativa: la fecha más temprana entre las filas que
        # aportaron a ese período (dayfirst=True, misma convención argentina
        # que periodos.py). Si ninguna parsea como fecha real (etiquetas
        # tipo "Marzo 2026"), se usa la primera fila en orden de aparición
        # — el dato numérico ya está bien; esto es sólo para mostrar.
        fechas = pd.to_datetime(crudas_periodo, dayfirst=True, format="mixed", errors="coerce")
        candidatas = pd.DataFrame({
            "clave": claves_periodo.to_numpy(),
            "cruda": crudas_periodo.to_numpy(),
            "fecha": fechas.to_numpy(),
        })
        for clave, grupo in candidatas.groupby("clave", sort=False):
            if clave not in serie:
                continue
            fila = grupo.loc[grupo["fecha"].idxmin()] if grupo["fecha"].notna().any() else grupo.iloc[0]
            etiquetas_originales[clave] = fila["cruda"]

    if (~es_periodo).any():
        # Guarda 2, sin cambios de comportamiento: agrupa por etiqueta cruda
        # (nunca por clave canónica, porque no la tiene) y aplica la misma
        # agregación — dos filas "TOTAL" idénticas siguen sumando entre sí.
        valores_resto = valores[~es_periodo]
        crudas_resto = periodos_crudos[~es_periodo]
        agrupado_resto = valores_resto.groupby(crudas_resto, sort=False)
        resultado_resto = agrupado_resto.mean() if agregacion == "avg" else agrupado_resto.sum(min_count=1)
        resultado_resto = resultado_resto.dropna()
        for etiqueta_cruda, valor in resultado_resto.items():
            no_reconocidos[str(etiqueta_cruda)] = round(float(valor), 4)

    if not serie:
        return None, {}, no_reconocidos

    orden = periodos.orden_cronologico(serie.keys())
    serie_ordenada = {k: serie[k] for k in orden}
    etiquetas_ordenadas = {k: etiquetas_originales[k] for k in orden}
    return serie_ordenada, etiquetas_ordenadas, no_reconocidos


def _df_base_y_periodo(df: pd.DataFrame, mapeo_hoja: dict) -> tuple[pd.DataFrame, Optional[str], int]:
    """Excluye filas_excluidas y resuelve la columna de período — lo
    comparten `aplicar_mapeo` y `extraer_tasas_declaradas` (reconciliación,
    Fase 3) para no repetir la lógica de índices dos veces."""
    orientacion = mapeo_hoja.get("orientacion", "periodos_en_filas")
    fila_encabezado = mapeo_hoja.get("fila_encabezado") or 0

    filas_excluidas_raw = mapeo_hoja.get("filas_excluidas") or []
    filas_excluidas = {
        i for i in (_a_indice_relativo(fila_encabezado, f) for f in filas_excluidas_raw)
        if i is not None and i in df.index
    }
    df_base = df.drop(index=list(filas_excluidas)) if filas_excluidas else df

    idx_periodo = _a_entero(mapeo_hoja.get("columna_periodo"))
    # "transaccional" también puede declarar columna_periodo (Fase 1): ahí
    # es una fecha por registro, no una etiqueta de mes por fila, pero
    # normalizar_periodo interpreta fechas completas igual de bien — es lo
    # que habilita armar una serie histórica desde una hoja transaccional
    # con columna de fecha en vez de descartar esa dimensión.
    col_periodo = df_base.columns[idx_periodo] if (
        orientacion in ("periodos_en_filas", "transaccional")
        and idx_periodo is not None and idx_periodo < len(df_base.columns)
    ) else None

    return df_base, col_periodo, fila_encabezado


def extraer_tasas_declaradas(df: pd.DataFrame, mapeo_hoja: dict) -> dict[int, "TasaDeclarada"]:
    """
    Reconciliación (Fase 3, hallazgo E): muchas planillas ya traen, al
    lado de los conteos crudos, la tasa/porcentaje calculado (ej. "Tasa
    no-show"). Esto la extrae para que reconciliacion.py la compare contra
    lo que da la fórmula del KPI con las variables ya extraídas — si no
    coinciden, algo se mapeó mal (típicamente: se tomó la columna de tasa
    en vez de la de conteo, o viceversa).

    Devuelve la serie completa además del valor vigente: derivacion.py la
    usa para reconstruir una variable faltante período por período, no
    solo para el mes actual.
    """
    df_base, col_periodo, _ = _df_base_y_periodo(df, mapeo_hoja)
    resultado: dict[int, TasaDeclarada] = {}
    for regla in mapeo_hoja.get("tasas_declaradas") or []:
        kpi_id = _a_entero(regla.get("kpi_id"))
        idx = _a_entero(regla.get("columna_index"))
        if kpi_id is None or idx is None or idx >= len(df_base.columns):
            continue
        col = df_base.columns[idx]
        valores = pd.to_numeric(df_base[col], errors="coerce")

        serie = None
        if col_periodo is not None:
            serie, _etiquetas, _no_reconocidos = _construir_serie_periodo(df_base, col, col_periodo, "avg")
            valor = list(serie.values())[-1] if serie else None
        else:
            no_nulos = valores.dropna()
            valor = float(no_nulos.iloc[-1]) if not no_nulos.empty else None

        if valor is None:
            continue

        # Una tasa puede venir como fracción (0.22) o ya en porcentaje
        # (22). Todo se normaliza a porcentaje acá — es la unidad en la que
        # trabajan las fórmulas de schema.py (_pct devuelve 0-100).
        factor = 100 if regla.get("unidad_origen") == "fraccion" else 1
        resultado[kpi_id] = TasaDeclarada(
            vigente=round(valor * factor, 2),
            serie={p: round(v * factor, 2) for p, v in serie.items()} if serie else None,
        )

    return resultado


# Unidades en las que un dato SÍ puede venir expresado como porcentaje.
# Hoy ninguna variable del vocabulario lo está (son conteos, montos, horas
# y minutos), así que en la práctica la guarda rechaza todo mapeo desde
# una columna con formato %. Se deja derivado de METRICAS en vez de
# hardcodear "rechazar siempre" para que la regla se ajuste sola si mañana
# se agrega una variable que sí sea un porcentaje.
UNIDADES_PORCENTUALES = {"porcentaje", "tasa"}


def _formato_incompatible(var: str, formato: Optional[str]) -> bool:
    """Guarda determinista: una columna formateada como % no puede ser el
    origen de una variable que no se mide en %. Es el hard stop contra el
    error que originó todo el plan (mapear "Tasa no-show" a `no_shows`,
    que es un conteo) — sin depender de que el modelo acierte."""
    if formato != "porcentaje":
        return False
    info = METRICAS.get(var)
    return (info.unidad_dato if info else None) not in UNIDADES_PORCENTUALES


def aplicar_mapeo(
    df: pd.DataFrame,
    mapeo_hoja: dict,
    variables: Optional[dict[str, VariableValue]] = None,
    formatos_columna: Optional[dict[int, str]] = None,
    registro_clientes: Optional[RegistroClientes] = None,
) -> dict[str, VariableValue]:
    """`registro_clientes` (Fase 2): si se pasa, las variables tipo dict
    marcadas `entidad="paciente"` en schema.py (hoy: ingreso_por_paciente)
    resuelven su columna de categoría contra matching.py antes de agrupar
    — el mismo RegistroClientes debe pasarse a través de TODOS los
    archivos de una misma migración para que la identidad de un paciente
    se reconozca entre hojas y entre archivos, no solo dentro de una hoja.
    Sin `registro_clientes` (default), el comportamiento es el de
    siempre: la categoría cruda tal cual, sin matching."""
    variables = dict(variables) if variables else {}
    hoja = mapeo_hoja.get("hoja")
    fuente = f"migracion_excel:{hoja}" if hoja else "migracion_excel"
    orientacion = mapeo_hoja.get("orientacion", "periodos_en_filas")
    # Fase H5: una hoja con una nota de "esto lo estima la recepcionista, no
    # hay sistema" pasa metodo="estimado" a TODAS sus variables — es una
    # propiedad de la hoja entera, no de una celda puntual, así que se
    # resuelve una sola vez acá (mismo lugar que fuente/orientacion).
    metodo = "estimado" if mapeo_hoja.get("hoja_estimada") else None
    df_base, col_periodo, fila_encabezado = _df_base_y_periodo(df, mapeo_hoja)

    for regla in mapeo_hoja["mapeo"]:
        var = regla.get("variable")
        if var is None or var not in VARIABLE_TYPES:
            continue
        tipo_var = VARIABLE_TYPES.get(var)
        if tipo_var in ("list", "ledger"):
            continue  # excel_parser nunca produce esto por mapeo columna-a-columna — ver VARIABLES_EXCEL

        if orientacion == "metricas_en_filas":
            fila_idx = _a_indice_relativo(fila_encabezado, regla.get("fila_index"))
            col_idx = _a_entero(regla.get("columna_index"))
            if fila_idx is None or fila_idx not in df_base.index or col_idx is None or col_idx >= len(df_base.columns):
                continue
            col = df_base.columns[col_idx]
            df_filtrado = df_base.loc[[fila_idx]]
            agregacion = "sum"  # una sola celda: sum de 1 fila = esa celda
            serie = None
            etiquetas_originales = None
            no_reconocidos = {}
        else:
            idx = _a_entero(regla.get("columna_index"))
            if idx is None or idx >= len(df_base.columns):
                continue
            # Guarda de formato: solo en esta rama, donde una columna
            # entera representa una variable. En "metricas_en_filas" el
            # formato dominante de la columna "Valor" mezcla unidades de
            # métricas distintas, así que no dice nada sobre la celda
            # puntual y aplicarlo daría falsos rechazos.
            if _formato_incompatible(var, (formatos_columna or {}).get(idx)):
                continue
            col = df_base.columns[idx]
            df_filtrado = df_base
            if regla.get("condicion"):
                try:
                    df_filtrado = df_filtrado.query(regla["condicion"])
                except Exception:
                    # Fase H6: si pandas no puede parsear la condición, la
                    # regla se descarta (la variable queda faltante y el
                    # wizard la pregunta) — antes acá había un `pass` que
                    # dejaba df_filtrado SIN FILTRAR y la regla se ejecutaba
                    # igual sobre todas las filas: con agregacion="sum" eso
                    # sumaba el total en vez de sólo las filas que cumplían
                    # la condición, un número mal en vez de un dato ausente.
                    continue
            agregacion = regla.get("agregacion", "sum")
            serie = None
            etiquetas_originales = None
            no_reconocidos = {}
            if col_periodo is not None and tipo_var in ("int", "float"):
                serie, etiquetas_originales, no_reconocidos = _construir_serie_periodo(
                    df_filtrado, col, col_periodo, agregacion,
                )

        if tipo_var == "dict":
            resolver_categoria = None
            if registro_clientes is not None and getattr(METRICAS.get(var), "entidad", None) == "paciente":
                # Closure: cada categoria (nombre crudo de la columna) pasa
                # por matching.py antes de agrupar. mypy/pandas no permite
                # pasar contexto extra a través de .map(), así que el
                # registro se captura por clausura en vez de por parámetro.
                def resolver_categoria(nombre, _registro=registro_clientes):
                    return encontrar_o_crear_cliente(nombre, _registro).cliente_id
            valor = _agregar_dict(
                df_filtrado, col, _a_entero(regla.get("columna_categoria_index")), df_base.columns, agregacion,
                resolver_categoria=resolver_categoria,
            )
        elif serie is not None:
            # Con serie disponible, el "valor vigente" es el ÚLTIMO período
            # real de la propia serie (no un promedio de todo el rango) —
            # esto es lo que cierra el hallazgo 1.1: nunca se muestra un
            # promedio inflado por la fila TOTAL como si fuera "el dato de
            # hoy".
            ultimo_periodo = list(serie.keys())[-1]
            valor = serie[ultimo_periodo]
        else:
            valor = _agregar_escalar(df_filtrado[col], agregacion)

        if valor is None:
            continue

        valor_pre_conversion = valor
        unidad_origen = regla.get("unidad_origen")
        factor = _factor_de_conversion(var, unidad_origen)
        valor = _convertir_unidad(var, valor, unidad_origen)
        if serie is not None:
            serie = _convertir_unidad(var, serie, unidad_origen)

        # Guarda defensiva: nunca guardar un tipo que no coincide con lo
        # que espera VARIABLE_TYPES (ver hallazgo B: la guarda original
        # solo cubría dict, no list — acá "list" ya se descartó arriba).
        if isinstance(valor, dict) != (tipo_var == "dict"):
            continue

        # Trazabilidad (Fase 0 del plan de evolución): registra de dónde
        # salió el valor sin cambiar el valor en sí — un "390 min" queda
        # explicable como "6.5 horas × 60, hoja X, fila/columna Y" en vez
        # de un número sin procedencia.
        traza = Trazabilidad(
            origen="celda",
            hoja=hoja,
            columna=str(col),
            fila=_a_entero(regla.get("fila_index")) if orientacion == "metricas_en_filas" else None,
            condicion=regla.get("condicion"),
            agregacion=agregacion,
            n_registros=len(df_filtrado) if hasattr(df_filtrado, "__len__") else None,
            filas_excluidas=list(mapeo_hoja.get("filas_excluidas") or []),
            unidad_origen=unidad_origen,
            unidad_final=METRICAS[var].unidad_dato if var in METRICAS else None,
            factor_conversion=factor,
            valor_pre_conversion=valor_pre_conversion if factor is not None else None,
            valor_final=valor,
        )

        nueva = VariableValue(
            valor=valor, fuente=fuente, confianza=regla.get("confianza", 0.8),
            serie=serie, periodo=(list(serie.keys())[-1] if serie else None),
            etiquetas_originales=etiquetas_originales,
            periodos_no_reconocidos=no_reconocidos or None,
            trazabilidad=traza,
            metodo=metodo,
        )
        existente = variables.get(var)
        if existente is None or nueva.confianza > existente.confianza:
            variables[var] = nueva

    return variables


def _armar_registros_ledger(df_base: pd.DataFrame, ledger_bloque: dict) -> list[dict]:
    """Fase H4b: convierte el bloque "ledger" del mapeo (columnas +
    eventos declarados por el modelo) en la lista plana de registros que
    ledger.construir_ledger_pacientes espera. Una fila puede producir más
    de un evento (ej. un presupuesto aceptado es "emitido" Y "aceptado"),
    por eso se itera "eventos" por fuera y las filas por dentro, no al
    revés."""
    idx_paciente = _a_entero(ledger_bloque.get("columna_paciente_index"))
    idx_fecha = _a_entero(ledger_bloque.get("columna_fecha_index"))
    if idx_paciente is None or idx_fecha is None:
        return []
    if idx_paciente >= len(df_base.columns) or idx_fecha >= len(df_base.columns):
        return []
    col_paciente = df_base.columns[idx_paciente]
    col_fecha = df_base.columns[idx_fecha]

    registros: list[dict] = []
    for evento in ledger_bloque.get("eventos") or []:
        tipo = evento.get("tipo_evento")
        if not tipo:
            continue
        df_evento = df_base
        if evento.get("condicion"):
            try:
                df_evento = df_evento.query(evento["condicion"])
            except Exception:
                # Misma decisión que H6 en aplicar_mapeo: una condición que
                # pandas no puede parsear descarta ESTE evento puntual, no
                # se genera para todas las filas sin filtrar.
                continue

        idx_monto = _a_entero(evento.get("columna_monto_index"))
        idx_tratamiento = _a_entero(evento.get("columna_tratamiento_index"))
        col_monto = df_base.columns[idx_monto] if idx_monto is not None and idx_monto < len(df_base.columns) else None
        col_tratamiento = (
            df_base.columns[idx_tratamiento]
            if idx_tratamiento is not None and idx_tratamiento < len(df_base.columns) else None
        )

        for _, fila in df_evento.iterrows():
            registro = {"paciente": fila[col_paciente], "fecha": fila[col_fecha], "tipo_evento": tipo}
            if col_monto is not None:
                registro["monto"] = fila[col_monto]
            if col_tratamiento is not None:
                registro["tratamiento"] = fila[col_tratamiento]
            registros.append(registro)

    return registros


def _fusionar_ledger(existente: Optional[dict], nuevo: dict) -> dict:
    """Varias hojas del mismo archivo pueden aportar ledger (ej. una hoja
    de turnos y otra de cobros) — se fusiona por paciente en vez de que la
    última pisara a la anterior, como pasaría con el criterio de "gana la
    mayor confianza" que usa el resto de las variables."""
    fusionado: dict[str, list[dict]] = {pid: list(eventos) for pid, eventos in (existente or {}).items()}
    for pid, eventos in nuevo.items():
        fusionado.setdefault(pid, []).extend(eventos)
    for pid in fusionado:
        fusionado[pid] = sorted(fusionado[pid], key=lambda e: e["periodo"])
    return fusionado


def parsear_excel(
    path: str, client: Optional["anthropic.Anthropic"] = None,
    registro_clientes: Optional[RegistroClientes] = None,
) -> tuple[dict[str, VariableValue], dict[int, TasaDeclarada]]:
    """Devuelve (variables, tasas_declaradas) — ver reconciliacion.py para
    qué hace pipeline.py con el segundo elemento.

    `registro_clientes` (Fase 2): pasar el MISMO RegistroClientes a través
    de todos los archivos de una migración (ver pipeline.procesar_migracion)
    para que "Juan Pérez" en un archivo y "J. Perez" en otro resuelvan al
    mismo paciente en vez de crear dos identidades distintas."""
    if client is None:
        assert anthropic is not None, "Instalar el SDK: pip install anthropic --break-system-packages"
        client = anthropic.Anthropic()

    hojas_crudas = leer_hojas_crudas(path)
    respuesta = pedir_mapeo_a_claude(hojas_crudas, client)
    formatos_por_hoja = {h.get("hoja"): h.get("formatos_columna") or {} for h in hojas_crudas}

    variables: dict[str, VariableValue] = {}
    tasas_declaradas: dict[int, TasaDeclarada] = {}
    for mapeo_hoja in respuesta["hojas"]:
        # Fase H4b: una hoja transaccional puede venir SOLO con "ledger" y
        # "mapeo" vacío (ninguna columna es un total agregable, todo el
        # valor está en el historial por paciente) — el `not mapeo` de
        # antes la hubiera saltado entera.
        if mapeo_hoja.get("fila_encabezado") is None or (not mapeo_hoja.get("mapeo") and not mapeo_hoja.get("ledger")):
            continue
        df = _releer_con_encabezado(path, mapeo_hoja.get("hoja"), mapeo_hoja["fila_encabezado"])
        formatos = formatos_por_hoja.get(mapeo_hoja.get("hoja")) or {}
        if mapeo_hoja.get("mapeo"):
            variables = aplicar_mapeo(df, mapeo_hoja, variables, formatos_columna=formatos, registro_clientes=registro_clientes)
        # Las tasas declaradas NO pasan por la guarda de formato: ahí un
        # formato % es justamente lo correcto y esperado.
        tasas_declaradas.update(extraer_tasas_declaradas(df, mapeo_hoja))

        ledger_bloque = mapeo_hoja.get("ledger")
        if ledger_bloque:
            df_base, _, _ = _df_base_y_periodo(df, mapeo_hoja)
            registros = _armar_registros_ledger(df_base, ledger_bloque)
            if registros:
                nuevo_ledger, _ = construir_ledger_pacientes(
                    registros, registro_clientes=registro_clientes,
                    campo_es_id_estable=bool(ledger_bloque.get("id_estable")),
                )
                # confianza es por evento (puede haber varios tipos en un
                # mismo bloque, ej. presupuesto_emitido + aceptado) — se
                # propaga la más baja, mismo criterio que min(confianza)
                # en cruces.py.
                confianza_nueva = min(
                    (e.get("confianza", 0.8) for e in ledger_bloque.get("eventos") or []),
                    default=0.8,
                )
                existente = variables.get("ledger_pacientes")
                hoja = mapeo_hoja.get("hoja")
                variables["ledger_pacientes"] = VariableValue(
                    valor=_fusionar_ledger(existente.valor if existente else None, nuevo_ledger),
                    fuente=f"migracion_excel:{hoja}" if hoja else "migracion_excel",
                    confianza=min(confianza_nueva, existente.confianza) if existente else confianza_nueva,
                )

    return variables, tasas_declaradas
