"""
probar_manual.py

Runner visual (Streamlit) para probar el pipeline completo contra archivos
reales y la API real de Claude, sin necesitar FastAPI, frontend ni Supabase
todavía.

Cubre las tres capas, en orden:
  1. Extracción y KPIs      — pipeline.procesar_migracion (Fases 0-3)
  2. Diagnóstico y oportunidades — diagnostico.py + catalogo_tecnologico.py +
     priorizacion.py (Fases 4-6), todo determinístico, sin llamar a la API
  3. Interpretación         — los tres entry points de interpretacion.py

Las respuestas de la Guía de Diagnóstico se cargan ANTES de procesar: son un
argumento de `procesar_migracion`, no un adorno del informe. Sin ellas el
pipeline devuelve `diagnostico=None` y la capa 2 entera no se ejecuta.

Correr desde agencia_ia_dental_dashboard/:
    source venv/bin/activate
    streamlit run parser/probar_manual.py

Necesita ANTHROPIC_API_KEY en el entorno o en un .env en la raíz del
proyecto — nunca hardcodeada acá.
"""

import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

from parser.pipeline import EXTRACTOR_POR_EXTENSION, procesar_migracion, resolver_conflicto
from parser.interpretacion.interpretacion import interpretar_clinica, interpretar_kpi, interpretar_panel
from parser.catalogo.cruces_propuestos import proponer_cruces
from parser.vocabulario.formato import fmt_ars, fmt_por_unidad
from parser.vocabulario.schema import KPI_BY_ID
from parser.interpretacion.explicaciones import explicar_cuarentena, explicar_derivada, explicar_discrepancia, nombre_humano

try:
    import anthropic
except ImportError:
    anthropic = None

load_dotenv()


def _server_iniciado_en() -> Optional[datetime]:
    """Fase I1: Streamlit re-ejecuta este script en cada interacción, pero los
    módulos importados (pipeline, excel_parser, vision_parser...) quedan
    cacheados en sys.modules desde que el PROCESO arrancó — un `streamlit run`
    dejado corriendo de una sesión anterior sigue sirviendo código viejo aunque
    los .py en disco ya cambiaron. `ps -o lstart=` da la hora real de arranque
    del proceso (no hay /proc en macOS para leerlo sin subprocess)."""
    try:
        salida = subprocess.check_output(
            ["ps", "-o", "lstart=", "-p", str(os.getpid())], text=True,
        ).strip()
        return datetime.strptime(salida, "%a %b %d %H:%M:%S %Y")
    except Exception:
        return None


def _codigo_mas_reciente_que(inicio: datetime) -> Optional[float]:
    """Mtime más nuevo entre los .py del parser (sin bajar a extractors/ni
    tests — alcanza con la carpeta principal para detectar un proceso viejo)."""
    base = Path(__file__).parent
    mtimes = [p.stat().st_mtime for p in base.glob("*.py")] + [p.stat().st_mtime for p in base.glob("extractors/*.py")]
    if not mtimes:
        return None
    mas_nuevo = max(mtimes)
    return mas_nuevo if mas_nuevo > inicio.timestamp() else None


st.set_page_config(page_title="Probar parser — Agencia IA Dental", layout="wide")
st.title("Probar el parser en vivo")

_inicio = _server_iniciado_en()
if _inicio is not None:
    _mtime_nuevo = _codigo_mas_reciente_que(_inicio)
    if _mtime_nuevo is not None:
        st.warning(
            f"⚠️ Este servidor arrancó el {_inicio:%Y-%m-%d %H:%M} y hay código modificado "
            f"después (el {datetime.fromtimestamp(_mtime_nuevo):%Y-%m-%d %H:%M}). Streamlit "
            f"re-ejecuta este archivo en cada interacción, pero los módulos importados "
            f"(pipeline, extractors/...) quedan en caché desde que el proceso arrancó — "
            f"reiniciá `streamlit run` para ver los cambios reales."
        )

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key or anthropic is None:
    st.error("No encontré ANTHROPIC_API_KEY (o falta instalar 'anthropic'). Cargala en .env antes de seguir.")
    st.stop()

client = anthropic.Anthropic(api_key=api_key)

if "resultado_migracion" not in st.session_state:
    st.session_state.resultado_migracion = None
# Fase F: cruces que el modelo propuso (capa 3) para esta migración, y qué
# decidió el profesional sobre cada uno ({índice: "aceptado" | "rechazado"}).
# Se resetean junto con resultado_migracion — una migración nueva invalida
# cualquier propuesta calculada sobre el set de variables anterior.
if "cruces_propuestos" not in st.session_state:
    st.session_state.cruces_propuestos = []
if "cruces_propuestos_decisiones" not in st.session_state:
    st.session_state.cruces_propuestos_decisiones = {}

st.subheader("1. Migración de datos")
# Fase I5: antes nunca se pasaba — el informe de la sección 8a salía sin
# nombre de clínica. Vive acá (sección 1) y no en la 8, mismo criterio que
# las respuestas de la Guía: es un dato de entrada, no un adorno del informe.
studio_nombre = st.text_input("Nombre de la clínica (opcional, para el informe de la sección 8a)")
extensiones = sorted(EXTRACTOR_POR_EXTENSION.keys())
archivos_subidos = st.file_uploader(
    f"Subí Excel/CSV/foto/PDF ({', '.join(extensiones)}). Dejalo vacío y procesá "
    "igual para simular el caso 'sin archivos' del Paso 3 opcional del onboarding.",
    type=[e.lstrip(".") for e in extensiones],
    accept_multiple_files=True,
)

# Las respuestas de la Guía se cargan ANTES de procesar, no después: son un
# argumento de procesar_migracion, no un adorno del informe final. Sin ellas
# el pipeline deja `diagnostico` y `oportunidades_priorizadas` en None y las
# Fases 4-6 (diagnostico.py, catalogo_tecnologico.py, priorizacion.py) no se
# ejecutan — que es exactamente lo que venía pasando: se cargaban en la
# sección 6, cuando la migración ya había corrido sin ellas.
respuestas_raw = st.text_area(
    "Respuestas de la Guía de Diagnóstico (opcional) — una línea por respuesta, "
    "formato 'P20: no hacemos seguimiento de presupuestos'. Sin esto no corre "
    "el motor de diagnóstico ni el catálogo de oportunidades.",
    height=110,
    key="respuestas_diagnostico",
)


def _parsear_respuestas() -> dict:
    respuestas = {}
    for linea in respuestas_raw.splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            respuestas[clave.strip()] = valor.strip()
    return respuestas


def _md(texto: str) -> str:
    """Escapa el `$` para que Streamlit no lo lea como delimitador de LaTeX.
    Con dos o más `$` en un mismo st.markdown/st.caption, KaTeX se come el
    texto del medio y lo muestra como fórmula — pasaba de verdad en la
    serie histórica de un cruce en ARS ("2026-01: $100.000, 2026-02: ..."
    renderizaba el "100.000, 2026-02: " en itálica matemática).
    Sólo hace falta en contextos markdown: `st.dataframe` no los interpreta."""
    return texto.replace("$", "\\$")


def _parsear_valor_manual(texto: str):
    """Intenta int, después float, y si no, deja el texto tal cual — mismo
    criterio laxo que el resto del harness: no se inventa un tipo, se
    prueba en orden y se usa lo primero que parsea."""
    texto = texto.strip()
    if not texto:
        return None
    try:
        return int(texto)
    except ValueError:
        pass
    try:
        return float(texto)
    except ValueError:
        pass
    return texto


if st.button("Procesar migración", type="primary"):
    # Se escribe cada archivo con su NOMBRE ORIGINAL dentro de un directorio
    # temporal, en vez de un NamedTemporaryFile con nombre aleatorio. Así
    # `archivo_origen` viaja como "presupuestos_abril_mayo2026.csv" y no como
    # "tmpz9yashn9.csv" — el nombre real aparece en conflictos, trazabilidad,
    # cuarentena y todo lo demás, que sólo repiten lo que el pipeline guardó.
    dir_temporal = tempfile.mkdtemp()
    paths_temporales = []
    for archivo in archivos_subidos or []:
        destino = os.path.join(dir_temporal, os.path.basename(archivo.name))
        with open(destino, "wb") as f:
            f.write(archivo.getvalue())
        paths_temporales.append(destino)

    respuestas = _parsear_respuestas()
    with st.spinner("Corriendo procesar_migracion contra la API real..."):
        try:
            st.session_state.resultado_migracion = procesar_migracion(
                paths_temporales,
                client=client,
                # None (no {}) cuando no se cargó ninguna: pipeline distingue
                # "el dueño no contestó nada" de "contestó y no dijo nada".
                respuestas_diagnostico=respuestas or None,
            )
            # Fase F: una migración nueva invalida cualquier cruce propuesto
            # sobre el set de variables anterior.
            st.session_state.cruces_propuestos = []
            st.session_state.cruces_propuestos_decisiones = {}
        except Exception as e:
            st.exception(e)
        finally:
            shutil.rmtree(dir_temporal, ignore_errors=True)

resultado = st.session_state.resultado_migracion

if resultado:
    # Archivos que el extractor no pudo procesar (excepción atrapada en
    # pipeline.procesar_migracion) — se muestran primero y sin expander:
    # que un documento falle no puede pasar desapercibido, el resto de la
    # migración sigue mostrándose igual con lo que sí se pudo extraer.
    if resultado.get("archivos_fallidos"):
        for fallo in resultado["archivos_fallidos"]:
            st.error(f"No se pudo procesar **{fallo['archivo']}**: {fallo['error']}")

    st.subheader("2. KPIs calculados")
    if resultado["kpis_calculados"]:
        filas = [
            {
                "KPI": info["kpi_nombre"],
                "Valor": fmt_por_unidad(info["valor"], info["unidad"]),
                "Confianza": info["confianza"],
                "Fuentes": ", ".join(info["fuentes"]),
                "Serie histórica": ", ".join(f"{p}: {v}" for p, v in info["serie"].items()) if info.get("serie") else "—",
            }
            for info in resultado["kpis_calculados"].values()
        ]
        st.dataframe(filas, use_container_width=True)

        st.markdown("**2a. ¿De dónde sale este número?**")
        st.caption(
            "Trazabilidad (Fase 0): qué celda, agregación y conversión de unidad "
            "componen cada variable de cada KPI — para poder auditar un valor raro "
            "sin volver a correr todo a mano."
        )
        for kpi_id, info in resultado["kpis_calculados"].items():
            with st.expander(f"{info['kpi_nombre']} — {_md(fmt_por_unidad(info['valor'], info['unidad']))}"):
                for var, texto in (info.get("trazabilidad_legible") or {}).items():
                    st.markdown(f"- **{var}**: {texto}")
    else:
        st.caption("Ninguno todavía — depende de qué variables falten.")

    if resultado.get("kpis_con_error"):
        st.subheader("2b. KPIs con error de cálculo")
        st.caption("No desaparecen en silencio — quedan acá con el motivo (ver plan de confiabilidad, hallazgo B).")
        for kpi_id, motivo in resultado["kpis_con_error"].items():
            st.error(f"KPI {kpi_id}: {motivo}")

    if resultado.get("variables_en_cuarentena"):
        st.subheader("2c. Variables en cuarentena")
        st.caption(
            "Datos que se extrajeron pero no pasaron las guardas de validacion.py o "
            "reconciliacion.py — no se usan para calcular ningún KPI hasta que se confirmen."
        )
        for v, info in resultado["variables_en_cuarentena"].items():
            resuelta = bool(info.get("reemplazada_por_derivacion"))
            with st.container(border=True):
                titulo = f"{'✅' if resuelta else '⚠️'} **{nombre_humano(v)}**"
                (st.success if resuelta else st.warning)(f"{titulo} — {_md(explicar_cuarentena(v, info))}")
                with st.expander("Ver detalle técnico"):
                    st.markdown(f"- **Variable**: `{v}`")
                    st.markdown(f"- **Valor extraído**: {info['valor']!r}")
                    st.markdown(f"- **Fuente**: {info['fuente']}")
                    st.markdown(f"- **Motivo técnico**: {info['motivo']}")

    if resultado.get("variables_derivadas"):
        st.subheader("2e. Variables derivadas de una tasa")
        st.caption(
            "La planilla no traía estas variables como columna, pero sí la tasa que las contiene: "
            "se despejaron algebraicamente. Se muestran siempre como dato a confirmar, nunca como "
            "valor observado."
        )
        for d in resultado["variables_derivadas"]:
            with st.container(border=True):
                st.info(f"**{nombre_humano(d['variable'])}** — {_md(explicar_derivada(d))}")
                with st.expander("Ver detalle técnico"):
                    st.markdown(
                        f"- **Variable**: `{d['variable']}` = {d['valor']!r}\n"
                        f"- **Despejada de**: `{d['desde_denominador']}` × tasa declarada "
                        f"{d['tasa_declarada']}% del KPI {d['kpi_id']} ({d.get('kpi_nombre') or '—'})"
                    )

    if resultado.get("discrepancias_reconciliacion"):
        st.subheader("2d. Discrepancias de reconciliación")
        st.caption("La tasa que calcula el KPI no coincide con la que la propia planilla ya declaraba al lado.")
        for d in resultado["discrepancias_reconciliacion"]:
            with st.container(border=True):
                st.warning(_md(explicar_discrepancia(d)))
                with st.expander("Ver detalle técnico"):
                    st.json(d)

    filas_rechazadas = [
        {"Variable": nombre, "Etiqueta en la hoja": etiqueta, "Valor que traía": valor}
        for nombre, vv in (resultado.get("variables") or {}).items()
        for etiqueta, valor in (getattr(vv, "periodos_no_reconocidos", None) or {}).items()
    ]
    if filas_rechazadas:
        st.subheader("2f. Filas que no son un período")
        st.caption(
            "Filas cuya etiqueta de período no resuelve a una clave canónica: notas al pie, "
            "TOTAL/Promedio que el modelo no listó en filas_excluidas. No entran a la serie "
            "histórica ni pueden ser el valor vigente — antes sí podían, y ahí salía el "
            "throughput = 0. Quedan acá para auditarlas."
        )
        st.dataframe(filas_rechazadas, use_container_width=True)

    calidad = resultado.get("calidad_datos")
    if calidad is not None:
        st.subheader("2g. Calidad del dato")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Completitud", f"{calidad.completitud_pct}%")
        c2.metric("Consistencia", f"{calidad.consistencia_pct}%")
        c3.metric(
            # Fase I2: confianza_promedio ya viene en escala 0-100 (calidad.py),
            # igual que completitud_pct y consistencia_pct — antes se mostraba
            # sin "%" y con :.2f, se leía "85.00" al lado de "60.0%".
            "Confianza prom.",
            "—" if calidad.confianza_promedio is None else f"{calidad.confianza_promedio:.0f}%",
        )
        c4.metric("En cuarentena", calidad.datos_en_cuarentena)
        if calidad.kpis_afectados:
            nombres = ", ".join(
                f"{KPI_BY_ID[k].nombre} (KPI {k})" if k in KPI_BY_ID else f"KPI {k}"
                for k in calidad.kpis_afectados
            )
            st.caption(f"KPIs afectados por datos en cuarentena: {nombres}")

    kpis_parciales = resultado.get("kpis_parciales") or {}
    kpis_esperando_facturas = resultado.get("kpis_esperando_facturas") or []
    kpis_bloqueados = resultado.get("kpis_bloqueados_por_diseno") or []
    kpis_en_conflicto = resultado.get("kpis_esperando_resolucion_conflicto") or {}
    if kpis_parciales or kpis_esperando_facturas or kpis_bloqueados or kpis_en_conflicto:
        st.subheader("2h. KPIs no calculados (y por qué)")
        st.caption(
            "El pipeline sabe exactamente por qué cada KPI no aparece en la sección 2 — "
            "esto nunca desaparece en silencio, es el mismo principio que las variables "
            "en cuarentena o las filas rechazadas de arriba."
        )
        filas_pendientes = (
            [{
                "KPI": f"{kid} — {KPI_BY_ID[kid].nombre}",
                "Motivo": "Falta un dato: " + ", ".join(vars_faltantes),
                "Categoría": "Falta info del wizard",
            } for kid, vars_faltantes in kpis_parciales.items()]
            + [{
                "KPI": f"{kid} — {KPI_BY_ID[kid].nombre}",
                "Motivo": "Requiere un export del sistema de cobros/agenda — nunca se pregunta en el wizard, nadie da estos números de memoria de forma confiable",
                "Categoría": "Esperando facturas",
            } for kid in kpis_esperando_facturas]
            + [{
                "KPI": f"{kid} — {KPI_BY_ID[kid].nombre}",
                "Motivo": "Lo calcula el propio sistema (comparación histórica, conteo interno) — nunca se pregunta",
                "Categoría": "Bloqueado por diseño",
            } for kid in kpis_bloqueados]
            + [{
                "KPI": f"{kid} — {KPI_BY_ID[kid].nombre}",
                "Motivo": "Dos fuentes dan valores distintos para: " + ", ".join(vars_en_conflicto),
                "Categoría": "Esperando resolver conflicto",
            } for kid, vars_en_conflicto in kpis_en_conflicto.items()]
        )
        st.dataframe(sorted(filas_pendientes, key=lambda f: f["Categoría"]), use_container_width=True)

    st.subheader("3. Preguntas pendientes del wizard")
    if resultado["preguntas_wizard"]:
        for p in resultado["preguntas_wizard"]:
            st.markdown(f"- **{p['variable']}** (desbloquea KPIs {p['kpis_que_desbloquea']}): {p['pregunta']}")
    else:
        st.caption("Ninguna — está todo cubierto.")

    st.subheader("4. Conflictos pendientes de confirmar")
    if resultado["conflictos_pendientes"]:
        for i, c in enumerate(resultado["conflictos_pendientes"]):
            if c.get("tipo") == "cobertura_distinta":
                # Fase E: dos fuentes con cobertura temporal distinta (una
                # con fecha, otra sin) — st.info en vez de st.warning porque
                # la pregunta misma ya aclara que puede no ser un error de
                # datos, sólo dos meses distintos.
                st.info(f"🗓️ **{c['variable']}**: {c['pregunta']}")
            elif c.get("tipo") == "contradice_confirmado":
                # Fase H1: un valor ya confirmado por el dueño, contradicho
                # por un archivo nuevo — sigue ganando la confirmación
                # (coverage.py ya la resolvió), esto es sólo el aviso.
                st.warning(f"🔒 **{c['variable']}**: {c['pregunta']}")
            else:
                st.warning(f"⚠️ **{c['variable']}**: {c['pregunta']}")

            # Fase I7: antes era un st.json crudo de las 4 claves viejas.
            # Ahora una tarjeta por candidato con la cuenta completa —
            # trazabilidad.explicar() ya sabe armar el texto, y desde I7
            # _candidato() también manda serie/período/etiquetas cuando
            # existen.
            if "tipo" in c:
                cols = st.columns(len(c["opciones"]))
                for col, cand in zip(cols, c["opciones"]):
                    with col:
                        st.markdown(f"**{cand['valor']}**")
                        st.caption(f"{cand.get('fuente', '?')} — archivo: {cand.get('archivo') or '—'}")
                        st.markdown(_md(cand.get("explicacion", "")))
                        if "serie" in cand:
                            st.caption(f"Serie: {cand['serie']}")
                            st.caption(f"Período vigente: {cand.get('periodo_vigente')}")
            else:
                st.json(c["opciones"])  # matches de identidad de paciente: otra forma, sin candidatos

            # Fase G5b: pipeline.resolver_conflicto ya existía y no
            # gastaba API (corre con archivos=[]) — sólo faltaba un botón.
            # Sólo para conflictos reales de variable (traen "tipo"); los
            # matches de identidad de paciente (sin "tipo", más abajo en
            # conflictos_pendientes) son otro mecanismo, fuera de acá.
            if "tipo" in c and c.get("permite_valor_manual"):
                # Fase I8: antes era un st.radio — sólo dejaba elegir UNO.
                # Ahora un checkbox por candidato: elegir 2+ los fusiona
                # (conflictos.fusionar_candidatos) en vez de forzar a
                # descartar el resto.
                seleccionados: list[int] = []
                for idx, cand in enumerate(c["opciones"]):
                    etiqueta = f"{cand['valor']} — {cand.get('fuente', '?')} (archivo: {cand.get('archivo') or '—'})"
                    if st.checkbox(etiqueta, key=f"check_conflicto_{i}_{idx}"):
                        seleccionados.append(idx)

                # Si se eligieron 2+ y alguno no tiene serie propia, hay
                # que preguntar a qué período corresponde — el sistema no
                # lo puede adivinar (ver docstring de fusionar_candidatos).
                periodos_de_escalares: dict[int, str] = {}
                if len(seleccionados) > 1:
                    for idx in seleccionados:
                        cand = c["opciones"][idx]
                        if "serie" not in cand:
                            periodo_str = st.text_input(
                                f"¿A qué período corresponde {cand['valor']} "
                                f"({cand.get('fuente', '?')})? (formato \"2026-03\")",
                                key=f"periodo_conflicto_{i}_{idx}",
                            )
                            if periodo_str.strip():
                                periodos_de_escalares[idx] = periodo_str.strip()

                valor_manual_str = st.text_input(
                    "…o un valor manual (opcional, gana sobre la selección de arriba — "
                    "ignora los checkboxes)",
                    key=f"valor_manual_conflicto_{i}",
                )
                if st.button(f"Resolver {c['variable']}", key=f"resolver_conflicto_{i}"):
                    valor_manual = _parsear_valor_manual(valor_manual_str)
                    kwargs = dict(
                        respuestas_diagnostico=_parsear_respuestas() or None,  # G5a: si no, se pierde el diagnóstico
                    )
                    if valor_manual is not None:
                        kwargs["valor_manual"] = valor_manual
                    elif seleccionados:
                        kwargs["candidatos"] = [c["opciones"][idx] for idx in seleccionados]
                        # periodos_de_escalares usa índices dentro de la
                        # lista fusionada, no dentro de c["opciones"] —
                        # hay que remapear.
                        kwargs["periodos_de_escalares"] = {
                            seleccionados.index(idx): periodo
                            for idx, periodo in periodos_de_escalares.items()
                        }
                    else:
                        st.warning("Elegí al menos un candidato o escribí un valor manual.")
                        kwargs = None
                    if kwargs is not None:
                        st.session_state.resultado_migracion = resolver_conflicto(
                            c["variable"], resultado["variables"], **kwargs,
                        )
                        st.rerun()
            st.divider()
    else:
        st.caption("Ninguno.")

    st.subheader("5. Variables de baja confianza a confirmar")
    if resultado["variables_a_confirmar"]:
        st.dataframe(resultado["variables_a_confirmar"], use_container_width=True)
    else:
        st.caption("Ninguna.")

    st.divider()
    st.subheader("6. Diagnóstico estructurado (determinístico, sin API)")
    st.caption(
        "Fases 4-6: diagnostico.py separa anomalía (hecho) de diagnóstico "
        "(interpretación) e hipótesis (conjetura), y nunca declara un estado más "
        "seguro de lo que los datos permiten. Todo esto se calcula en Python — "
        "Claude interpreta después, recibiéndolo como input."
    )
    diagnosticos = resultado.get("diagnostico")
    if not diagnosticos:
        st.info(
            "Sin diagnóstico: cargá las respuestas de la Guía en la sección 1 antes de "
            "procesar. Sin ellas no hay contexto cualitativo contra el cual cruzar el gap, "
            "y el pipeline no ejecuta diagnostico.py ni el catálogo de oportunidades."
        )
    else:
        _COLOR = {
            "CRITICAL": "🔴", "PROBLEM": "🟠", "WATCH": "🟡",
            "NORMAL": "⚪", "HEALTHY": "🟢", "INSUFFICIENT_EVIDENCE": "⚫",
        }
        # `.value`: EstadoEvidencia es un str-Enum, así que compara e indexa
        # como string, pero al interpolarlo rinde "EstadoEvidencia.WATCH".
        st.dataframe(
            [{
                "KPI": d.kpi_id,
                "Problema": d.problema,
                "Estado": f"{_COLOR.get(d.estado, '')} {d.estado.value}",
                "Confianza": round(d.confianza, 2),
                "Anomalías": len(d.anomalias),
                "Contradicciones": len(d.contradicciones),
            } for d in diagnosticos],
            use_container_width=True,
        )
        for d in diagnosticos:
            with st.expander(f"{_COLOR.get(d.estado, '')} KPI {d.kpi_id} — {d.problema} ({d.estado.value})"):
                st.markdown("**Hechos**")
                for h in d.hechos:
                    st.markdown(f"- {h}")
                for a in d.anomalias:
                    st.markdown(
                        f"**Anomalía** — magnitud {a.magnitud_pct}%, "
                        f"benchmark: `{a.confiabilidad_benchmark}`"
                    )
                for c in d.contradicciones:
                    st.warning(f"**Contradicción** ({', '.join(c.preguntas_involucradas)}): {c.descripcion}")
                for p in d.patrones_cruzados:
                    st.info(f"**Patrón cruzado**: {p}")
                for hip in d.hipotesis:
                    st.markdown(
                        f"**Hipótesis** (confianza {hip.confianza}) — {hip.causa_probable}. "
                        f"Sustentada en: {', '.join(hip.preguntas_que_la_sustentan) or '—'}"
                    )
                for falta in d.informacion_faltante:
                    st.caption(f"Información faltante: {falta}")

    st.subheader("7. Oportunidades priorizadas")
    st.caption(
        "catalogo_tecnologico.py mapea cada diagnóstico a intervenciones concretas y "
        "priorizacion.py las ordena por score (impacto × addressability × suficiencia)."
    )
    oportunidades = resultado.get("oportunidades_priorizadas")
    if not oportunidades:
        st.caption("Ninguna — depende del diagnóstico de la sección 6.")
    else:
        # Fase I4: tabla resumen para escanear de un vistazo — el detalle
        # completo (por qué se recomienda, qué necesita, cuándo medirla)
        # va en la tarjeta expandible de abajo, no acá.
        st.dataframe(
            [{
                "Score": round(o.score, 3),
                "Intervención": o.oportunidad.intervencion.nombre,
                "Tipo": o.oportunidad.intervencion.tipo,
                "Etapa": o.oportunidad.intervencion.etapa,
                "KPI": o.kpi_id,
                "Addressability": round(o.oportunidad.addressability, 2),
            } for o in oportunidades],
            use_container_width=True,
        )

        for o in oportunidades:
            interv = o.oportunidad.intervencion
            diag = o.oportunidad.diagnostico
            with st.expander(f"{interv.nombre} — score {round(o.score, 3)}"):
                # Por qué: el problema detectado + las hipótesis de causa
                # probable que ya calculó diagnostico.py (Fase 4-6) — antes
                # esto existía en el payload y la sección 7 no lo mostraba.
                st.markdown(f"**Por qué te lo recomendamos**")
                st.markdown(f"- {diag.problema}")
                for hip in diag.hipotesis:
                    st.markdown(f"- {hip.causa_probable} _(confianza {hip.confianza})_")

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Qué hace**")
                    st.markdown(interv.como_funciona or "—")
                    st.markdown("**Qué necesita**")
                    st.markdown(interv.condicion)
                    if interv.requiere_compliance:
                        st.warning(f"⚖️ {interv.requiere_compliance}")
                with col2:
                    st.markdown("**Qué mejora**")
                    st.markdown(f"{interv.beneficio or '—'}\n\n_(métrica: {interv.metrica_objetivo})_")
                    st.markdown("**Cuándo medir si funcionó**")
                    st.markdown(f"A las {interv.periodo_evaluacion_semanas} semanas de implementada.")
                    if interv.durabilidad:
                        st.info(f"⚠️ Riesgo conocido: {interv.durabilidad}")

    st.divider()
    st.subheader("8. Interpretación del asistente")
    if resultado["kpis_calculados"]:
        st.caption(
            "Usa las mismas respuestas de la Guía cargadas en la sección 1. "
            "Estos tres entry points sí llaman a la API."
        )
        respuestas = _parsear_respuestas()

        st.markdown(
            "**8a. Informe de la clínica** — el entry point completo: 10 secciones armadas "
            "sobre el diagnóstico y las oportunidades ya calculados arriba. Único de los tres "
            "que corre con thinking adaptativo, porque sí es razonamiento."
        )
        if not diagnosticos:
            st.caption("Necesita el diagnóstico de la sección 6.")
        elif st.button("Generar informe de la clínica"):
            with st.spinner("Llamando a interpretar_clinica (streaming) contra la API real..."):
                try:
                    resultado_informe = interpretar_clinica(
                        diagnosticos=diagnosticos,
                        oportunidades_priorizadas=oportunidades or [],
                        calidad_datos=resultado.get("calidad_datos"),
                        respuestas_diagnostico=respuestas,
                        studio_nombre=studio_nombre or None,
                        # Fase I5: antes el informe sólo veía calidad_datos
                        # agregado — ahora también los casos puntuales que
                        # ya se le explican al dueño en las secciones 2c/
                        # 2d/2e, para que la sección 7 del informe pueda
                        # nombrarlos en vez de hablar en abstracto.
                        variables_en_cuarentena=resultado.get("variables_en_cuarentena"),
                        discrepancias_reconciliacion=resultado.get("discrepancias_reconciliacion"),
                        variables_derivadas=resultado.get("variables_derivadas"),
                        conflictos_pendientes=resultado.get("conflictos_pendientes"),
                        client=client,
                    )
                except Exception as e:
                    st.exception(e)
                    resultado_informe = None
            if resultado_informe:
                if resultado_informe.get("truncado"):
                    st.warning(
                        "El informe se cortó por max_tokens — lo de abajo está incompleto, "
                        "no es el informe final."
                    )
                st.markdown(resultado_informe["informe"])
                with st.expander("Ver payload enviado al asistente"):
                    st.json(resultado_informe["payload_enviado_al_asistente"])

        st.markdown("**8b. Panel completo** — el asistente ve todos los KPIs a la vez y puede cruzarlos entre sí.")
        if st.button("Interpretar panel completo"):
            with st.spinner("Llamando a interpretar_panel contra la API real..."):
                try:
                    resultado_panel = interpretar_panel(
                        kpis_calculados=resultado["kpis_calculados"],
                        respuestas_diagnostico=respuestas,
                        # Sin esto el modelo tenía que re-derivar del payload crudo
                        # los patrones cruzados y contradicciones que diagnostico.py
                        # ya calculó (ver regla 8 de SYSTEM_PROMPT_BASE).
                        diagnostico=diagnosticos,
                        client=client,
                    )
                except Exception as e:
                    st.exception(e)
                    resultado_panel = None
            if resultado_panel:
                if resultado_panel.get("truncado"):
                    st.warning("La respuesta se cortó por max_tokens — está incompleta.")
                st.markdown("**Diagnóstico del asistente (panel):**")
                st.write(resultado_panel["interpretacion"])
                with st.expander("Ver payload enviado al asistente"):
                    st.json(resultado_panel["payload_enviado_al_asistente"])

        st.markdown("**8c. Zoom a un solo KPI**")
        kpi_ids = list(resultado["kpis_calculados"].keys())
        kpi_elegido = st.selectbox(
            "KPI a interpretar",
            kpi_ids,
            format_func=lambda kid: resultado["kpis_calculados"][kid]["kpi_nombre"],
        )

        if st.button("Interpretar este KPI"):
            info_kpi = resultado["kpis_calculados"][kpi_elegido]
            with st.spinner("Llamando a interpretar_kpi contra la API real..."):
                try:
                    resultado_interp = interpretar_kpi(
                        kpi_id=kpi_elegido,
                        valor_clinica=info_kpi["valor"],
                        respuestas_diagnostico=respuestas,
                        serie_historica=info_kpi.get("serie"),
                        client=client,
                    )
                except Exception as e:
                    st.exception(e)
                    resultado_interp = None
            if resultado_interp:
                if resultado_interp.get("truncado"):
                    st.warning("La respuesta se cortó por max_tokens — está incompleta.")
                st.markdown("**Diagnóstico del asistente:**")
                st.write(resultado_interp["interpretacion"])
                with st.expander("Ver payload enviado al asistente"):
                    st.json(resultado_interp["payload_enviado_al_asistente"])
    else:
        st.caption("Todavía no hay ningún KPI calculado para interpretar.")

    st.divider()
    st.subheader("9. Cruces determinísticos (fuera del catálogo de 21 KPIs)")
    st.caption(
        "cruces.py (Fase B): métricas que ninguna de las 21 KPIFormula fijas calcula, "
        "generadas de dos formas, ambas sin llamar a la API — nunca mezcladas con la "
        "sección 2 de arriba, porque un cruce no tiene benchmark ni kpi_id."
    )
    # Fase F: un cruce propuesto que el profesional aceptó se ve exactamente
    # igual que uno determinístico — se fusiona acá, no se le agrega ninguna
    # marca especial (ya pasó por la misma validación de calcular_cruce).
    cruces_aceptados = [
        c for i, c in enumerate(st.session_state.cruces_propuestos)
        if st.session_state.cruces_propuestos_decisiones.get(i) == "aceptado"
    ]
    cruces = (resultado.get("cruces") or []) + cruces_aceptados
    if not cruces:
        st.caption(
            "Ninguno todavía — necesita al menos dos variables con serie histórica que "
            "compartan unidad compatible (\\$/conteo, \\$/horas, \\$/\\$ o conteo/conteo dentro "
            "del embudo) y al menos 2 períodos en común."
        )
    else:
        st.dataframe(
            [{
                "Cruce": c.nombre,
                "Valor (último período)": fmt_por_unidad(c.valor, c.unidad),
                "Origen": {"embudo": "Embudo declarado", "algebra": "Álgebra de unidades", "propuesto": "Propuesto por IA"}.get(c.origen, c.origen),
                "Períodos": c.periodos_comunes,
                "Confianza": c.confianza,
            } for c in cruces],
            use_container_width=True,
        )
        for c in cruces:
            with st.expander(f"{c.nombre} — {_md(fmt_por_unidad(c.valor, c.unidad))}"):
                st.markdown(f"**Fórmula**: `{c.variable_a} {c.operacion} {c.variable_b}`")
                st.markdown(f"**Por qué es válido**: {c.justificacion}")
                st.markdown(
                    "**Serie histórica**: " + ", ".join(f"{p}: {_md(fmt_por_unidad(v, c.unidad))}" for p, v in c.serie.items())
                )

    st.markdown("**9b. Cruces propuestos por IA (a confirmar)**")
    st.caption(
        "cruces_propuestos.py (Fase C): el modelo sugiere qué cruzar y por qué le "
        "importaría al dueño — nunca calcula el número, eso lo hace calcular_cruce igual "
        "que en la sección 9. Llamada aparte a la API, no se dispara sola."
    )
    if st.button("🤖 Proponer cruces con IA"):
        with st.spinner("Llamando a proponer_cruces contra la API real..."):
            try:
                st.session_state.cruces_propuestos = proponer_cruces(resultado["variables"], client=client)
                st.session_state.cruces_propuestos_decisiones = {}
            except Exception as e:
                st.exception(e)

    cruces_propuestos = st.session_state.cruces_propuestos
    if not cruces_propuestos:
        st.caption("Ninguno todavía — apretá el botón de arriba, o el modelo no propuso nada esta vez.")
    else:
        decisiones = st.session_state.cruces_propuestos_decisiones
        for i, c in enumerate(cruces_propuestos):
            decision = decisiones.get(i)
            with st.container(border=True):
                st.markdown(f"**{c.nombre}** — {_md(fmt_por_unidad(c.valor, c.unidad))}")
                st.markdown(f"**Etapa del embudo:** {c.etapa_embudo}")
                st.markdown(f"**Cómo ayuda a decidir:** {c.impacto_decision}")
                if decision == "aceptado":
                    st.success("✅ Aceptado — ya está en la tabla de la sección 9.")
                    if st.button("Revertir", key=f"revertir_{i}"):
                        del decisiones[i]
                        st.rerun()
                elif decision == "rechazado":
                    st.error("❌ Descartado.")
                    if st.button("Revertir", key=f"revertir_{i}"):
                        del decisiones[i]
                        st.rerun()
                else:
                    col_aceptar, col_descartar = st.columns(2)
                    if col_aceptar.button("✅ Aceptar", key=f"aceptar_{i}"):
                        decisiones[i] = "aceptado"
                        st.rerun()
                    if col_descartar.button("❌ Descartar", key=f"descartar_{i}"):
                        decisiones[i] = "rechazado"
                        st.rerun()

    st.subheader("10. Métricas de paciente (ledger_pacientes)")
    st.caption(
        "metricas_paciente.py (Fase H4c): 17 métricas longitudinales que las 21 KPIFormula "
        "fijas no pueden expresar (necesitan historial por paciente, no un agregado "
        "mensual) — determinístico, sin API. Sección separada a propósito, mismo criterio "
        "que la 9: contrato distinto, nunca mezclado con los KPIs de arriba."
    )
    metricas_paciente = resultado.get("metricas_paciente")
    if metricas_paciente is None:
        st.caption(
            "Sin datos todavía — ningún archivo de esta migración trajo un historial por "
            "paciente (identificador de paciente + fecha por fila, ej. un export de cobros "
            "o de turnos)."
        )
    else:
        ltv = metricas_paciente["ltv_real"]
        concentracion = metricas_paciente["concentracion_ingresos"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Pacientes con LTV registrado", len(ltv))
        col2.metric("LTV total", fmt_ars(sum(ltv.values())) if ltv else "-")
        col3.metric(
            "Concentración de ingresos",
            f"{concentracion['share_ingresos'] * 100:.0f}% en el top {concentracion['n_pacientes_top']}"
            if concentracion else "-",
        )

        etiquetas = {
            "no_show_recurrente": "No-show recurrente (≥30% de sus turnos, mín. 3)",
            "pacientes_en_riesgo_de_fuga": "En riesgo de fuga (6 a 14 meses sin actividad)",
            "porcentaje_base_inactiva": "% de la base inactiva (14+ meses sin actividad)",
            "dias_desde_ultimo_contacto": "Días desde el último contacto",
            "ltv_real": "LTV real (suma de pagos)",
            "ticket_promedio_por_cliente": "Ticket promedio por paciente",
            "concentracion_ingresos": "Concentración de ingresos (top 10%)",
            "mix_tratamientos_por_paciente": "Mix de tratamientos por paciente",
            "retencion_por_cohorte_alta": "Retención por cohorte de alta (%)",
            "intervalo_medio_entre_visitas": "Intervalo medio entre visitas (meses)",
            "abandono_a_mitad_tratamiento": "Tratamiento abandonado a mitad de camino",
            "nuevos_vs_recurrentes": "Nuevos vs. recurrentes (período vigente)",
            "atribucion_referidos": "Referidos traídos, por paciente",
            "tasa_segunda_visita": "Tasa de segunda visita (%)",
            "velocidad_presupuesto_a_aceptacion": "Meses de presupuesto a aceptación",
            "multi_tratamiento_vs_mono": "Multi-tratamiento vs. mono-tratamiento (%)",
            "estacionalidad_observada_por_paciente": "No-shows por mes calendario",
        }
        with st.expander("Ver las 17 métricas completas"):
            for clave, etiqueta in etiquetas.items():
                valor = metricas_paciente.get(clave)
                st.markdown(f"**{etiqueta}**")
                if valor is None:
                    st.caption("Sin datos suficientes para calcularla.")
                elif isinstance(valor, dict) and valor:
                    st.dataframe(
                        [{"Paciente / clave": k, "Valor": v} for k, v in valor.items()],
                        use_container_width=True,
                    )
                elif isinstance(valor, list) and valor:
                    st.write(valor)
                else:
                    st.caption("Vacío — sin eventos del tipo que esta métrica necesita.")
