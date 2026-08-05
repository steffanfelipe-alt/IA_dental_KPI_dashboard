"""
pipeline.py

Punto de entrada único del parser. Lo llama el endpoint de FastAPI del
Paso 3 del onboarding (o cualquier carga posterior de datos):

    resultado = procesar_migracion(archivos, variables_previas=...)

Flujo:
  1. Por cada archivo, elige el extractor según extensión.
  2. Resuelve conflictos entre todos los archivos y variables_previas (lo
     que ya estaba en la base de la clínica — de una migración anterior,
     del wizard, o de facturas ya cargadas): si dos fuentes dan valores
     distintos con confianza empatada, la variable queda pendiente de que
     el dueño decida (ver conflictos.py), no se elige por orden de llegada.
  3. Corre el chequeo de cobertura y arma la respuesta para el frontend:
     KPIs ya calculados + preguntas pendientes ordenadas por impacto +
     conflictos pendientes de confirmación.
"""

from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from parser.vocabulario.schema import KPI_BY_ID
from parser.diagnostico.calidad import evaluar_calidad
from parser.catalogo.catalogo_tecnologico import mapear_oportunidades
from parser.catalogo.cruces import generar_cruces
from parser.cobertura_calidad.coverage import VariableValue, evaluar_cobertura, variables_para_wizard
from parser.cobertura_calidad.conflictos import fusionar_candidatos, resolver_conflictos
from parser.diagnostico.diagnostico import diagnosticar
from parser.pacientes.matching import RegistroClientes
from parser.diagnostico.priorizacion import priorizar_oportunidades
from parser.cobertura_calidad.validacion import validar_variable, validar_identidades
from parser.cobertura_calidad.reconciliacion import reconciliar
from parser.cobertura_calidad.derivacion import derivar_variables_faltantes
from parser.extraccion import segunda_lectura
from parser.extraccion import geometria
from parser.extraccion.estrategias import (
    EstrategiaExtraccion, ExtraccionExcel, ExtraccionVisionImagen, ExtraccionVisionPDF,
)
from parser.pacientes import metricas_paciente
from parser.interpretacion.explicaciones import nombre_humano
from parser.extraccion import excel_parser, vision_parser
from parser.vocabulario.puerto_llm import PuertoLLM
from parser.vocabulario.puerto_geometria import PuertoGeometria


# Una sola instancia de cada estrategia alcanza — son sin estado, sólo
# envuelven las funciones de extraccion/excel_parser.py y
# extraccion/vision_parser.py.
_EXTRACCION_EXCEL = ExtraccionExcel()
_EXTRACCION_IMAGEN = ExtraccionVisionImagen()
_EXTRACCION_PDF = ExtraccionVisionPDF()

EXTRACTOR_POR_EXTENSION: dict[str, EstrategiaExtraccion] = {
    ".xlsx": _EXTRACCION_EXCEL,
    ".xls": _EXTRACCION_EXCEL,
    ".csv": _EXTRACCION_EXCEL,
    ".png": _EXTRACCION_IMAGEN,
    ".jpg": _EXTRACCION_IMAGEN,
    ".jpeg": _EXTRACCION_IMAGEN,
    ".webp": _EXTRACCION_IMAGEN,
    ".pdf": _EXTRACCION_PDF,
}


def extraer_archivo(
    path: str, puerto_llm: Optional[PuertoLLM] = None, registro_clientes: Optional[RegistroClientes] = None,
) -> tuple[dict[str, VariableValue], dict[int, object]]:
    """
    Devuelve (variables, tasas_declaradas) a partir de la
    `EstrategiaExtraccion` que corresponda a la extensión del archivo.

    Antes esto normalizaba a mano la forma del resultado
    (`isinstance(resultado, tuple)`, porque excel_parser devolvía
    (variables, tasas_declaradas) y vision_parser sólo variables) y
    decidía por introspección (`inspect.signature`) si el extractor
    soportaba `registro_clientes`. Con `ResultadoExtraccion` y el
    contrato explícito de `EstrategiaExtraccion.extraer` (Fase Strategy),
    ninguna de las dos cosas hace falta: toda estrategia devuelve la misma
    forma y acepta `registro_clientes` siempre, aunque algunas lo
    ignoren.
    """
    ext = Path(path).suffix.lower()
    estrategia = EXTRACTOR_POR_EXTENSION.get(ext)
    if estrategia is None:
        raise ValueError(f"Formato no soportado: {ext}. Soportados: {list(EXTRACTOR_POR_EXTENSION)}")
    resultado = estrategia.extraer(path, puerto_llm, registro_clientes=registro_clientes)
    nombre_archivo = Path(path).name
    variables = {var: replace(valor, archivo_origen=nombre_archivo) for var, valor in resultado.variables.items()}
    return variables, resultado.tasas_declaradas


def _nombre_candidato(c: dict) -> str:
    """De qué archivo/hoja habla un candidato de conflicto — ya usa el
    dict enriquecido por conflictos._candidato (Fase I7): `archivo` si lo
    tiene, si no `fuente` (ej. "confirmado_por_dueno" para un valor que el
    dueño ya había confirmado, sin archivo)."""
    return c.get("archivo") or c.get("fuente") or "una fuente sin identificar"


def _pregunta_legible(c) -> str:
    """Fase I7: antes eran 3 f-strings genéricas que nunca decían qué
    archivo, qué valor, ni qué período — "Encontramos X en dos archivos
    con valores distintos. ¿Cuál usamos?" sin un solo dato concreto. Ahora
    arma la pregunta con los datos reales de `c.candidatos`, que desde
    I7 ya trae `serie`/`periodo_vigente`/`explicacion` por candidato."""
    nombre = nombre_humano(c.variable)
    if c.tipo == "cobertura_distinta":
        con_serie = [cand for cand in c.candidatos if "serie" in cand]
        sin_serie = [cand for cand in c.candidatos if "serie" not in cand]
        cobertura = ", ".join(
            f"{_nombre_candidato(cand)} (hasta {cand.get('periodo_vigente')})" for cand in con_serie
        ) or "un archivo"
        totales = ", ".join(
            f"{cand['valor']} en {_nombre_candidato(cand)}" for cand in sin_serie
        ) or "otro archivo"
        return (
            f"\"{nombre}\": {cobertura} trae una serie mensual, y {totales} da un total "
            f"sin fecha — puede que hablen de meses distintos, no necesariamente un error. "
            f"¿Cuál usamos?"
        )
    if c.tipo == "contradice_confirmado":
        confirmado, *discrepantes = c.candidatos
        valores_nuevos = ", ".join(f"{d['valor']} ({_nombre_candidato(d)})" for d in discrepantes)
        return (
            f"Ya habías confirmado \"{nombre}\" = {confirmado['valor']}, pero "
            f"{valores_nuevos} dice otra cosa. ¿Mantenemos tu confirmación o la actualizamos?"
        )
    valores = ", ".join(f"{cand['valor']} ({_nombre_candidato(cand)})" for cand in c.candidatos)
    return f"\"{nombre}\": encontramos valores distintos — {valores}. ¿Cuál es correcto?"


def _filtrar_por_validacion(
    variables: dict[str, VariableValue],
) -> tuple[dict[str, VariableValue], dict[str, dict]]:
    """
    Corre las guardas de validacion.py sobre lo que salió de
    resolver_conflictos. Lo que no pasa NO se descarta en silencio: sale
    del dict `variables` (así evaluar_cobertura lo trata como si faltara,
    y el wizard lo vuelve a preguntar) y queda documentado en
    `variables_en_cuarentena` con el motivo del rechazo, para poder
    auditar qué pasó en vez de que el dato quede simplemente ausente sin
    explicación.
    """
    aceptadas: dict[str, VariableValue] = {}
    cuarentena: dict[str, dict] = {}

    for var, vv in variables.items():
        motivo = validar_variable(var, vv.valor, vv.fuente)
        if motivo:
            cuarentena[var] = {"valor": vv.valor, "fuente": vv.fuente, "motivo": motivo}
        else:
            aceptadas[var] = vv

    escalares = {v: vv.valor for v, vv in aceptadas.items() if isinstance(vv.valor, (int, float))}
    for rechazo in validar_identidades(escalares):
        vv = aceptadas.pop(rechazo.variable, None)
        if vv is not None:
            cuarentena[rechazo.variable] = {"valor": vv.valor, "fuente": vv.fuente, "motivo": rechazo.motivo}

    return aceptadas, cuarentena


def _segunda_lectura_para_variables_dudosas(
    variables: dict[str, VariableValue],
    variables_ya_reconciliadas: set[str],
    archivos: list[str],
    puerto_llm: Optional[PuertoLLM],
) -> dict[str, VariableValue]:
    """
    Última red del plan de confiabilidad (Fase 3): lo que queda con
    confianza baja y que reconciliacion.py no pudo cruzar contra una tasa
    declarada se manda a una segunda lectura independiente
    (segunda_lectura.py). Si coincide, sube la confianza; si no, se
    deja la confianza baja tal cual — no se elige a ciegas cuál lectura es
    la correcta, eso ya lo muestra el sistema como "a confirmar"
    (variables_a_confirmar en el payload final).
    """
    if puerto_llm is None:
        return variables

    a_verificar = segunda_lectura.variables_a_verificar(variables, variables_ya_reconciliadas)
    if not a_verificar:
        return variables

    archivo_por_nombre = {Path(a).name: a for a in archivos}
    variables = dict(variables)

    # Bug #2 (E2E): una foto/PDF no tiene grid de Excel para releer — antes
    # SIEMPRE se llamaba excel_parser.leer_hojas_crudas(path) para toda
    # variable dudosa, que para un PNG/JPG/PDF tira una excepción (no es un
    # archivo de Excel) -> se capturaba en silencio -> la variable de foto
    # quedaba sin segunda lectura para siempre. Se separa por
    # `fuente == "migracion_foto"` ANTES de agrupar por hoja: las de foto
    # van por pedir_segunda_lectura_imagen (releer la imagen entera con
    # vision_parser), las de planilla siguen exactamente el camino de
    # siempre.
    a_verificar_foto = [v for v in a_verificar if variables[v].fuente == "migracion_foto"]
    a_verificar_planilla = [v for v in a_verificar if v not in a_verificar_foto]

    por_archivo_foto: dict[str, list[str]] = {}
    for var in a_verificar_foto:
        vv = variables[var]
        if not vv.archivo_origen or vv.archivo_origen not in archivo_por_nombre:
            continue
        por_archivo_foto.setdefault(vv.archivo_origen, []).append(var)

    for nombre_archivo, vars_de_foto in por_archivo_foto.items():
        path = archivo_por_nombre[nombre_archivo]
        try:
            lecturas = segunda_lectura.pedir_segunda_lectura_imagen(path, vars_de_foto, puerto_llm)
        except Exception:
            continue
        confianza_actualizada, _discrepancias = segunda_lectura.contrastar(variables, lecturas)
        for var, nueva_confianza in confianza_actualizada.items():
            variables[var] = replace(variables[var], confianza=nueva_confianza)

    grids_cache: dict[str, list[dict]] = {}
    por_hoja: dict[tuple[str, Optional[str]], list[str]] = {}
    for var in a_verificar_planilla:
        vv = variables[var]
        if not vv.archivo_origen or vv.archivo_origen not in archivo_por_nombre:
            continue
        hoja = vv.fuente.split(":", 1)[1] if ":" in vv.fuente else None
        por_hoja.setdefault((vv.archivo_origen, hoja), []).append(var)

    for (nombre_archivo, hoja), vars_de_hoja in por_hoja.items():
        path = archivo_por_nombre[nombre_archivo]
        if path not in grids_cache:
            try:
                grids_cache[path] = excel_parser.leer_hojas_crudas(path)
            except Exception:
                grids_cache[path] = []
        hojas = grids_cache[path]
        if not hojas:
            continue
        grid = next((h["grid"] for h in hojas if h.get("hoja") == hoja), hojas[0]["grid"])

        try:
            lecturas = segunda_lectura.pedir_segunda_lectura(grid, vars_de_hoja, puerto_llm)
        except Exception:
            continue
        confianza_actualizada, _discrepancias = segunda_lectura.contrastar(variables, lecturas)
        for var, nueva_confianza in confianza_actualizada.items():
            variables[var] = replace(variables[var], confianza=nueva_confianza)

    return variables


def _verificacion_geometria_fotos(
    variables: dict[str, VariableValue],
    archivos: list[str],
    puerto_geometria: Optional[PuertoGeometria],
) -> dict[str, VariableValue]:
    """
    Bug #1a: verificación de geometría independiente para fotos — mismo
    rol estructural que _segunda_lectura_para_variables_dudosas (misma
    forma try/except alrededor de la llamada externa, mismo patrón de
    resolución de path vía archivo_por_nombre), pero contra layout real
    (geometria.contrastar_filas) en vez de una relectura semántica.

    A diferencia de la segunda lectura, corre para TODA variable
    `migracion_foto` de la foto (no solo las de confianza dudosa): es un
    chequeo geométrico independiente, no una segunda opinión reservada
    para lo que ya se ve dudoso (Requirement "Photo triggers geometry
    pass" del spec).

    Con `puerto_geometria=None` (default de procesar_migracion — el único
    valor que se pasa hoy en producción, porque el adapter real está
    bloqueado, ver Fase 5 de tasks.md) esto es un no-op completo: la
    salida queda byte-idéntica a la de antes de este cambio.
    """
    if puerto_geometria is None:
        return variables

    archivo_por_nombre = {Path(a).name: a for a in archivos}
    variables = dict(variables)

    por_archivo_foto: dict[str, list[str]] = {}
    for var, vv in variables.items():
        if vv.fuente != "migracion_foto":
            continue
        if not vv.archivo_origen or vv.archivo_origen not in archivo_por_nombre:
            continue
        por_archivo_foto.setdefault(vv.archivo_origen, []).append(var)

    for nombre_archivo, vars_de_foto in por_archivo_foto.items():
        path = archivo_por_nombre[nombre_archivo]
        try:
            filas_geometricas = puerto_geometria.ordenar_filas(path)
        except Exception:
            continue
        variables_de_foto = {var: variables[var] for var in vars_de_foto}
        confianza_actualizada, _discrepancias = geometria.contrastar_filas(variables_de_foto, filas_geometricas)
        for var, nueva_confianza in confianza_actualizada.items():
            variables[var] = replace(variables[var], confianza=nueva_confianza)

    return variables


def procesar_migracion(
    archivos: list[str],
    variables_previas: Optional[dict[str, VariableValue]] = None,
    puerto_llm: Optional[PuertoLLM] = None,
    respuestas_diagnostico: Optional[dict[str, str]] = None,
    puerto_geometria: Optional[PuertoGeometria] = None,
) -> dict:
    """
    Devuelve el payload listo para el frontend:
      {
        "kpis_calculados": {id: {...}},
        "kpis_parciales": {id: [variables_que_faltan]},
        "kpis_bloqueados_por_diseno": [ids],   # se calculan solos, no se muestran como "pendiente"
        "kpis_esperando_facturas": [ids],
        "kpis_esperando_resolucion_conflicto": {id: [variables_en_conflicto]},
        "archivos_fallidos": [ {archivo, error} ],  # extractor tiró excepción, no se pudo leer ese archivo
        "preguntas_wizard": [ {variable, tipo, kpis_que_desbloquea, prioridad} ],
        "conflictos_pendientes": [ {variable, tipo, pregunta, opciones, permite_valor_manual} ],
        "variables_a_confirmar": [ ... ],       # baja confianza, mostrar como sugerencia
        "variables": {...},                     # snapshot completo para guardar en la DB
        "calidad_datos": ReporteCalidad(...),   # Fase 3: completitud/consistencia/confianza agregados
        "diagnostico": [Diagnostico(...)] | None,            # Fase 4, solo si se pasa respuestas_diagnostico
        "oportunidades_priorizadas": [OportunidadPriorizada(...)] | None,  # Fases 5-6, idem
      }

    `respuestas_diagnostico` (opcional, Fase 4-6): si se pasan las
    respuestas de la Guía de Diagnóstico, además de los KPIs se devuelve
    el diagnóstico estructurado (diagnostico.py) y las oportunidades del
    catálogo tecnológico ya priorizadas (catalogo_tecnologico.py +
    priorizacion.py) — antes de esta fase, ninguno de los tres módulos lo
    llamaba nadie en producción. Sin este argumento (default None), el
    comportamiento es exactamente el de antes: ambas claves quedan en
    None y no se ejecuta nada nuevo.

    `puerto_geometria` (opcional, Bug #1a): verificación de geometría
    independiente para variables de foto, ver
    `_verificacion_geometria_fotos`. Default `None` — el único valor que
    se pasa hoy en producción, porque el adapter real
    (`AdaptadorGeometriaVendor`) está bloqueado (Fase 5 de tasks.md) —
    hace que este paso sea un no-op completo, sin cambiar el
    comportamiento de antes de este cambio.
    """
    # Un solo RegistroClientes para TODA la migración (Fase 2): así "Juan
    # Pérez" en un archivo y "J. Perez" en otro resuelven al mismo
    # paciente, no solo dentro de una misma hoja.
    registro_clientes = RegistroClientes()
    extraidas_por_archivo = []
    archivos_fallidos: list[dict[str, str]] = []
    for a in archivos:
        try:
            extraidas_por_archivo.append(extraer_archivo(a, puerto_llm, registro_clientes=registro_clientes))
        except Exception as exc:
            # Un archivo problemático (ej. una foto ambigua que hace que
            # vision_parser no pueda parsear el JSON de Claude) no puede
            # tirar abajo una migración de varios documentos donde el resto
            # sí es procesable — mismo criterio que cruces_propuestos.py
            # aplica a un ítem mal formado dentro de un lote, llevado a
            # nivel archivo completo. Antes se perdía TODA la migración por
            # un solo documento raro.
            archivos_fallidos.append({"archivo": Path(a).name, "error": str(exc)})
    extraidas = [variables for variables, _ in extraidas_por_archivo]
    tasas_declaradas: dict[int, object] = {}
    for _, tasas in extraidas_por_archivo:
        tasas_declaradas.update(tasas)

    # Fase H4b: un ledger nunca pasa por resolver_conflictos. Esa función
    # compara candidatos por IGUALDAD de `.valor` para decidir un ganador
    # — funciona para un escalar o un dict plano, pero un ledger es un
    # dict de LISTAS (no hasheable, ni comparable con sentido: dos
    # archivos con historial de paciente no "compiten" por la misma
    # respuesta, cada uno aporta eventos propios). Se saca de `extraidas`
    # ANTES de resolver_conflictos y se fusiona acá — con lo que ya
    # hubiera en variables_previas también, por si una migración anterior
    # ya había poblado un ledger — dejando un único valor ya fusionado
    # que se inyecta después de resolver_conflictos, en el mismo punto
    # donde habría caído si hubiera ganado sin discusión.
    ledgers = [v.pop("ledger_pacientes") for v in extraidas if "ledger_pacientes" in v]
    ledger_previo = (variables_previas or {}).get("ledger_pacientes")
    if ledger_previo is not None:
        ledgers.insert(0, ledger_previo)
    ledger_fusionado: Optional[VariableValue] = None
    if ledgers:
        fusionado: dict[str, list[dict]] = {}
        for lv in ledgers:
            for pid, eventos in lv.valor.items():
                fusionado.setdefault(pid, []).extend(eventos)
        for pid in fusionado:
            fusionado[pid] = sorted(fusionado[pid], key=lambda e: e["periodo"])
        ledger_fusionado = replace(ledgers[-1], valor=fusionado, confianza=min(lv.confianza for lv in ledgers))

    variables_previas_sin_ledger = {k: v for k, v in (variables_previas or {}).items() if k != "ledger_pacientes"}
    variables, conflictos = resolver_conflictos([variables_previas_sin_ledger, *extraidas])
    if ledger_fusionado is not None:
        variables["ledger_pacientes"] = ledger_fusionado
    variables, variables_en_cuarentena = _filtrar_por_validacion(variables)
    variables_en_conflicto = {c.variable for c in conflictos}

    # Reconciliación (Fase 3, hallazgo E): recalcula cada tasa % con las
    # variables ya aceptadas y la compara contra la que la propia planilla
    # declara. Lo que no cierra se pone en cuarentena — esto atrapa el
    # caso real donde un conteo pasa todas las guardas de tipo/rango pero
    # implica una tasa que no tiene nada que ver con la que la hoja
    # declara al lado (ej. no_shows mal mapeado).
    a_cuarentena_reconciliacion, discrepancias = reconciliar(variables, tasas_declaradas)
    for var in a_cuarentena_reconciliacion:
        vv = variables.pop(var, None)
        if vv is not None:
            # Fase I2: antes el motivo era un string constante, igual para
            # toda variable, sin decir qué KPI ni cuánto se alejaba. Se deja
            # el string de siempre (nada lo dejó de usar) y se agrega
            # "discrepancia" al lado, aditivo, con los números reales — es
            # lo que explicaciones.py usa para armar el texto humano.
            disc = next((d for d in discrepancias if var in d.variables), None)
            variables_en_cuarentena[var] = {
                "valor": vv.valor, "fuente": vv.fuente,
                "motivo": (
                    f"la tasa declarada en la planilla no coincide con lo calculado "
                    f"a partir de esta variable (ver discrepancias_reconciliacion)"
                ),
                "discrepancia": {
                    "kpi_id": disc.kpi_id, "kpi_nombre": disc.kpi_nombre,
                    "calculado": disc.calculado, "declarado": disc.declarado,
                } if disc else None,
            }

    # Derivación (punto 1 del plan de cierre): completa una variable que la
    # planilla no trae como columna cruda pero que se despeja de una tasa
    # que sí trae calculada (ej. no_shows desde "Tasa no-show" × turnos).
    # Va DESPUÉS de reconciliar a propósito: una variable derivada
    # satisface la identidad de su tasa por construcción, así que dejarla
    # entrar antes haría que ese KPI cerrara siempre y diera por
    # corroborada a su compañera sin verificarla nunca.
    nuevas_derivadas, derivaciones = derivar_variables_faltantes(variables, tasas_declaradas)
    variables.update(nuevas_derivadas)

    # Si una variable había caído en cuarentena y después se pudo derivar,
    # se deja el registro (es la traza de auditoría: "el 57 extraído se
    # rechazó") pero marcado como reemplazado, para que el panel no muestre
    # el rechazo y el valor nuevo como si se contradijeran.
    for var in nuevas_derivadas:
        if var in variables_en_cuarentena:
            variables_en_cuarentena[var]["reemplazada_por_derivacion"] = True
            variables_en_cuarentena[var]["motivo"] += " — reemplazada por un valor derivado de la tasa"

    variables_ya_reconciliadas = {
        v for kpi_id in tasas_declaradas if kpi_id in KPI_BY_ID for v in KPI_BY_ID[kpi_id].variables
    }
    # Las derivadas no se releen: no están escritas en la hoja (son un
    # despeje), así que una segunda lectura no tendría de dónde sacarlas.
    variables_ya_reconciliadas |= set(nuevas_derivadas)
    variables = _segunda_lectura_para_variables_dudosas(variables, variables_ya_reconciliadas, archivos, puerto_llm)
    variables = _verificacion_geometria_fotos(variables, archivos, puerto_geometria)

    # Fase H4c: si hay ledger_pacientes, ltv_real() es una suma real de
    # eventos "pago" ya extraídos de filas concretas — no un despeje
    # algebraico como derivacion.py, así que NO se marca fuente=derivado
    # (eso la treaparía en confianza 0.6 como si fuera una estimación).
    # Antes de evaluar_cobertura a propósito: ahí se decide si KPI 14 cae
    # en kpis_calculados o en kpis_esperando_facturas. Nunca pisa un valor
    # ya extraído o del wizard (mismo criterio que derivacion.py).
    ledger_vv = variables.get("ledger_pacientes")
    if ledger_vv is not None and "ingreso_por_paciente" not in variables:
        ingreso = metricas_paciente.ltv_real(ledger_vv.valor)
        if ingreso:
            variables["ingreso_por_paciente"] = VariableValue(
                valor=ingreso, fuente="ledger_pacientes",
                confianza=ledger_vv.confianza, archivo_origen=ledger_vv.archivo_origen,
            )

    cobertura = evaluar_cobertura(variables, variables_en_conflicto)
    preguntas = variables_para_wizard(cobertura)

    resultado = {
        "kpis_calculados": {
            kpi_id: {**info, "kpi_nombre": KPI_BY_ID[kpi_id].nombre}
            for kpi_id, info in cobertura.kpis_calculados.items()
        },
        "kpis_parciales": cobertura.kpis_parciales,
        "kpis_bloqueados_por_diseno": cobertura.kpis_bloqueados_por_diseno,
        "kpis_esperando_facturas": cobertura.kpis_esperando_facturas,
        "kpis_esperando_resolucion_conflicto": cobertura.kpis_esperando_resolucion_conflicto,
        "kpis_con_error": cobertura.kpis_con_error,
        "archivos_fallidos": archivos_fallidos,
        "variables_en_cuarentena": variables_en_cuarentena,
        "variables_derivadas": [
            {
                "variable": d.variable, "valor": d.valor, "kpi_id": d.kpi_id,
                "kpi_nombre": KPI_BY_ID[d.kpi_id].nombre if d.kpi_id in KPI_BY_ID else None,
                "desde_denominador": d.desde_denominador, "tasa_declarada": d.tasa_declarada,
            }
            for d in derivaciones
        ],
        "discrepancias_reconciliacion": [
            {
                "kpi_id": d.kpi_id, "kpi_nombre": d.kpi_nombre,
                "calculado": d.calculado, "declarado": d.declarado, "variables": d.variables,
            }
            for d in discrepancias
        ],
        "preguntas_wizard": preguntas,
        "conflictos_pendientes": [
            {
                "variable": c.variable,
                "tipo": c.tipo,
                # Fase I7: la pregunta ahora nombra archivos, valores y
                # períodos reales — antes eran 3 f-strings genéricas sin un
                # solo dato concreto (ver _pregunta_legible).
                "pregunta": _pregunta_legible(c),
                "opciones": c.candidatos,
                "permite_valor_manual": True,
            }
            for c in conflictos
        ] + [
            # Fase 2: matches de identidad de paciente en zona gris — el
            # mismo canal que un conflicto de variable, mismo principio
            # ("ante empate, decide el dueño, no el sistema"). Nunca se
            # fusionaron solos; acá se muestran para que el dueño confirme.
            {
                "variable": "identidad_paciente",
                "pregunta": f"¿\"{amb['nombre']}\" es la misma persona que \"{amb['candidato_existente']}\"?",
                "opciones": [
                    {"valor": "misma_persona", "descripcion": f"Sí, es {amb['candidato_existente']}"},
                    {"valor": "persona_distinta", "descripcion": "No, es alguien distinto"},
                ],
                "permite_valor_manual": False,
                "similitud": amb["similitud"],
            }
            for amb in registro_clientes.ambiguos
        ],
        "variables_a_confirmar": [
            {"variable": v, "valor_sugerido": variables[v].valor, "fuente": variables[v].fuente}
            for v in cobertura.variables_baja_confianza
        ],
        "variables": variables,
    }
    # Fase 3 (Data Quality Report): pura agregación de lo que ya está en
    # `resultado` — no dispara ninguna extracción ni llamada a Claude.
    resultado["calidad_datos"] = evaluar_calidad(resultado)

    # Fase B: cruces determinísticos fuera de las 21 KPIFormula (ver
    # cruces.py). Corre siempre, con o sin respuestas_diagnostico —
    # a diferencia de las Fases 4-6, no depende de contexto cualitativo.
    # Clave aparte a propósito: un Cruce no tiene kpi_id y no entra a
    # evaluar_cobertura, diagnosticar ni priorizar_oportunidades.
    resultado["cruces"] = generar_cruces(variables)

    # Fase H4c: las 17 métricas de metricas_paciente.py, fuera de las 20
    # KPIFormula por el mismo motivo que los cruces (docstring del
    # módulo) — clave aparte, nunca entra a evaluar_cobertura ni a
    # evaluar_calidad (que ya corrió arriba, así que esto no le cambia el
    # input). None si no hay ledger, no {} — para que la UI distinga
    # "sin datos de paciente todavía" de "el ledger está vacío".
    resultado["metricas_paciente"] = (
        metricas_paciente.calcular_todas(ledger_vv.valor) if ledger_vv is not None else None
    )

    # Fases 4-6: diagnóstico estructurado + oportunidades del catálogo ya
    # priorizadas. Todo determinista, sin llamar a Claude — eso lo hace
    # interpretacion.py después, recibiendo este diagnóstico como input
    # (ver SYSTEM_PROMPT_BASE regla 8). Solo corre si el llamador pasó
    # respuestas de la Guía de Diagnóstico; sin eso no hay con qué cruzar
    # el gap y no tiene sentido diagnosticar nada.
    if respuestas_diagnostico is not None:
        diagnosticos = diagnosticar(resultado["kpis_calculados"], respuestas_diagnostico, variables=variables)
        oportunidades = mapear_oportunidades(diagnosticos, contexto_clinica=respuestas_diagnostico)
        # impacto parejo (1.0) por default: ese criterio de negocio sigue
        # sin recalcularse acá (mismo principio que priorizar_kpis) — el
        # llamador puede pasar su propio impacto_por_kpi más adelante si
        # hace falta discriminar entre KPIs.
        impacto_por_kpi = {d.kpi_id: 1.0 for d in diagnosticos}
        resultado["diagnostico"] = diagnosticos
        resultado["oportunidades_priorizadas"] = priorizar_oportunidades(oportunidades, impacto_por_kpi, top_n=5)
    else:
        resultado["diagnostico"] = None
        resultado["oportunidades_priorizadas"] = None

    return resultado


def resolver_conflicto(
    variable: str,
    variables_previas: dict[str, VariableValue],
    valor: Any = None,
    valor_manual: Any = None,
    respuestas_diagnostico: Optional[dict[str, str]] = None,
    candidatos: Optional[list[dict]] = None,
    periodos_de_escalares: Optional[dict[int, str]] = None,
) -> dict:
    """
    Aplica la elección del dueño de la clínica sobre un conflicto pendiente
    (POST /onboarding/{clinica_id}/resolver-conflicto, ver README) y vuelve
    a correr procesar_migracion con esa variable ya confirmada.

    Fase G5a: `respuestas_diagnostico` faltaba acá — sin reenviarlas,
    `procesar_migracion` corre con el default `None` y las Fases 4-6
    (diagnostico.py, catalogo_tecnologico.py, priorizacion.py) no se
    ejecutan. Efecto real: el dueño resolvía un conflicto para GANAR un
    KPI y en el mismo movimiento PERDÍA el diagnóstico y las oportunidades
    que ya tenía calculados. Default `None` a propósito — aditivo, ningún
    call-site existente ni el endpoint documentado cambian de
    comportamiento si no lo pasan.

    Fase I8: `candidatos` es la forma nueva — una lista de 1+ candidato-
    dicts (la misma forma que arma `conflictos._candidato()`, con `serie`
    si el candidato la tiene). Reemplaza a `valor`/`valor_manual` cuando
    se usa. Con 1 candidato, arregla un bug real: el camino viejo
    (`valor`) siempre construía un `VariableValue` escalar pelado, así que
    "elegir" un candidato con 6 meses de historia le destruía la serie en
    el mismo movimiento que la confirmaba. Con 2+, es "elegir los dos":
    se fusionan por período en vez de forzar una elección — ver
    `conflictos.fusionar_candidatos`. `valor`/`valor_manual` siguen
    funcionando exactamente igual que siempre cuando `candidatos` no se
    pasa, para no romper ningún llamador existente.
    """
    if candidatos:
        fusion = fusionar_candidatos(candidatos, periodos_de_escalares)
        nueva = VariableValue(
            valor=fusion["valor"], fuente="confirmado_por_dueno", confianza=1.0,
            archivo_origen=None, serie=fusion["serie"], periodo=fusion["periodo"],
            etiquetas_originales=fusion["etiquetas_originales"],
        )
    else:
        valor_elegido = valor if valor_manual is None else valor_manual
        nueva = VariableValue(valor=valor_elegido, fuente="confirmado_por_dueno", confianza=1.0, archivo_origen=None)

    variables_actualizadas = dict(variables_previas)
    variables_actualizadas[variable] = nueva
    return procesar_migracion(
        archivos=[], variables_previas=variables_actualizadas,
        respuestas_diagnostico=respuestas_diagnostico,
    )


def sin_archivos(variables_previas: Optional[dict[str, VariableValue]] = None) -> dict:
    """
    Caso "no subís nada" del onboarding (Paso 3 opcional): corre el mismo
    chequeo de cobertura solo contra lo que ya hubiera (normalmente nada),
    así el wizard termina preguntando el set completo — sin código aparte.
    """
    return procesar_migracion(archivos=[], variables_previas=variables_previas)
