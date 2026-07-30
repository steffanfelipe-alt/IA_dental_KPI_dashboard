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

import inspect
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from schema import KPI_BY_ID
from calidad import evaluar_calidad
from catalogo_tecnologico import mapear_oportunidades
from cruces import generar_cruces
from coverage import VariableValue, evaluar_cobertura, variables_para_wizard
from conflictos import resolver_conflictos
from diagnostico import diagnosticar
from matching import RegistroClientes
from priorizacion import priorizar_oportunidades
from validacion import validar_variable, validar_identidades
from reconciliacion import reconciliar
from derivacion import derivar_variables_faltantes
import segunda_lectura
from extractors import excel_parser, vision_parser


EXTRACTOR_POR_EXTENSION = {
    ".xlsx": excel_parser.parsear_excel,
    ".xls": excel_parser.parsear_excel,
    ".csv": excel_parser.parsear_excel,
    ".png": vision_parser.parsear_imagen,
    ".jpg": vision_parser.parsear_imagen,
    ".jpeg": vision_parser.parsear_imagen,
    ".webp": vision_parser.parsear_imagen,
    ".pdf": vision_parser.parsear_pdf,
}


def extraer_archivo(
    path: str, client=None, registro_clientes: Optional[RegistroClientes] = None,
) -> tuple[dict[str, VariableValue], dict[int, object]]:
    """
    Devuelve (variables, tasas_declaradas). No todos los extractores
    conocen tasas_declaradas (hoy solo excel_parser, ver reconciliacion.py
    — vision_parser sigue devolviendo solo variables): se normaliza acá
    para que pipeline.py no necesite saber qué extractor se usó.

    `registro_clientes` (Fase 2, matching.py): solo se pasa a extractores
    que lo soportan (hoy: excel_parser.parsear_excel) — se detecta por
    firma en vez de hardcodear "si es excel_parser", así un extractor
    nuevo que lo declare se engancha solo, sin tocar este módulo.
    """
    ext = Path(path).suffix.lower()
    extractor = EXTRACTOR_POR_EXTENSION.get(ext)
    if extractor is None:
        raise ValueError(f"Formato no soportado: {ext}. Soportados: {list(EXTRACTOR_POR_EXTENSION)}")
    kwargs = {}
    if registro_clientes is not None and "registro_clientes" in inspect.signature(extractor).parameters:
        kwargs["registro_clientes"] = registro_clientes
    resultado = extractor(path, client, **kwargs)
    if isinstance(resultado, tuple):
        variables, tasas_declaradas = resultado
    else:
        variables, tasas_declaradas = resultado, {}
    nombre_archivo = Path(path).name
    variables = {var: replace(valor, archivo_origen=nombre_archivo) for var, valor in variables.items()}
    return variables, tasas_declaradas


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
    client,
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
    if client is None:
        return variables

    a_verificar = segunda_lectura.variables_a_verificar(variables, variables_ya_reconciliadas)
    if not a_verificar:
        return variables

    archivo_por_nombre = {Path(a).name: a for a in archivos}
    grids_cache: dict[str, list[dict]] = {}

    por_hoja: dict[tuple[str, Optional[str]], list[str]] = {}
    for var in a_verificar:
        vv = variables[var]
        if not vv.archivo_origen or vv.archivo_origen not in archivo_por_nombre:
            continue
        hoja = vv.fuente.split(":", 1)[1] if ":" in vv.fuente else None
        por_hoja.setdefault((vv.archivo_origen, hoja), []).append(var)

    variables = dict(variables)
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
            lecturas = segunda_lectura.pedir_segunda_lectura(grid, vars_de_hoja, client)
        except Exception:
            continue
        confianza_actualizada, _discrepancias = segunda_lectura.contrastar(variables, lecturas)
        for var, nueva_confianza in confianza_actualizada.items():
            variables[var] = replace(variables[var], confianza=nueva_confianza)

    return variables


def procesar_migracion(
    archivos: list[str],
    variables_previas: Optional[dict[str, VariableValue]] = None,
    client=None,
    respuestas_diagnostico: Optional[dict[str, str]] = None,
) -> dict:
    """
    Devuelve el payload listo para el frontend:
      {
        "kpis_calculados": {id: {...}},
        "kpis_parciales": {id: [variables_que_faltan]},
        "kpis_bloqueados_por_diseno": [ids],   # se calculan solos, no se muestran como "pendiente"
        "kpis_esperando_facturas": [ids],
        "kpis_esperando_resolucion_conflicto": {id: [variables_en_conflicto]},
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
    """
    # Un solo RegistroClientes para TODA la migración (Fase 2): así "Juan
    # Pérez" en un archivo y "J. Perez" en otro resuelven al mismo
    # paciente, no solo dentro de una misma hoja.
    registro_clientes = RegistroClientes()
    extraidas_por_archivo = [extraer_archivo(a, client, registro_clientes=registro_clientes) for a in archivos]
    extraidas = [variables for variables, _ in extraidas_por_archivo]
    tasas_declaradas: dict[int, object] = {}
    for _, tasas in extraidas_por_archivo:
        tasas_declaradas.update(tasas)

    variables, conflictos = resolver_conflictos([variables_previas or {}, *extraidas])
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
            variables_en_cuarentena[var] = {
                "valor": vv.valor, "fuente": vv.fuente,
                "motivo": (
                    f"la tasa declarada en la planilla no coincide con lo calculado "
                    f"a partir de esta variable (ver discrepancias_reconciliacion)"
                ),
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
    variables = _segunda_lectura_para_variables_dudosas(variables, variables_ya_reconciliadas, archivos, client)

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
        "variables_en_cuarentena": variables_en_cuarentena,
        "variables_derivadas": [
            {
                "variable": d.variable, "valor": d.valor, "kpi_id": d.kpi_id,
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
                # Fase E: un conflicto tipo="cobertura_distinta" (una fuente
                # trae fecha, la otra no — ver conflictos.resolver_conflictos)
                # no es necesariamente un error de datos: puede que las dos
                # fuentes hablen de meses distintos. La pregunta lo dice así
                # en vez de sugerir que uno de los dos números está mal.
                "pregunta": (
                    f"Encontramos {c.variable} en dos archivos con valores distintos, pero "
                    f"uno trae fecha y el otro no — puede que hablen de meses distintos, no "
                    f"necesariamente un error. ¿Cuál usamos?"
                ) if c.tipo == "cobertura_distinta" else (
                    f"Encontramos valores distintos para {c.variable}. ¿Cuál es correcto?"
                ),
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

    # Fase B: cruces determinísticos fuera de las 20 KPIFormula (ver
    # cruces.py). Corre siempre, con o sin respuestas_diagnostico —
    # a diferencia de las Fases 4-6, no depende de contexto cualitativo.
    # Clave aparte a propósito: un Cruce no tiene kpi_id y no entra a
    # evaluar_cobertura, diagnosticar ni priorizar_oportunidades.
    resultado["cruces"] = generar_cruces(variables)

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
) -> dict:
    """
    Aplica la elección del dueño de la clínica sobre un conflicto pendiente
    (POST /onboarding/{clinica_id}/resolver-conflicto, ver README) y vuelve
    a correr procesar_migracion con esa variable ya confirmada.
    """
    valor_elegido = valor if valor_manual is None else valor_manual
    variables_actualizadas = dict(variables_previas)
    variables_actualizadas[variable] = VariableValue(
        valor=valor_elegido, fuente="confirmado_por_dueno", confianza=1.0, archivo_origen=None,
    )
    return procesar_migracion(archivos=[], variables_previas=variables_actualizadas)


def sin_archivos(variables_previas: Optional[dict[str, VariableValue]] = None) -> dict:
    """
    Caso "no subís nada" del onboarding (Paso 3 opcional): corre el mismo
    chequeo de cobertura solo contra lo que ya hubiera (normalmente nada),
    así el wizard termina preguntando el set completo — sin código aparte.
    """
    return procesar_migracion(archivos=[], variables_previas=variables_previas)
