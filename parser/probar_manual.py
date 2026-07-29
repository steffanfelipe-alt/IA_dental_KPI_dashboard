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
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from pipeline import EXTRACTOR_POR_EXTENSION, procesar_migracion
from interpretacion import interpretar_clinica, interpretar_kpi, interpretar_panel
from formato import fmt_por_unidad

try:
    import anthropic
except ImportError:
    anthropic = None

load_dotenv()

st.set_page_config(page_title="Probar parser — Agencia IA Dental", layout="wide")
st.title("Probar el parser en vivo")

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key or anthropic is None:
    st.error("No encontré ANTHROPIC_API_KEY (o falta instalar 'anthropic'). Cargala en .env antes de seguir.")
    st.stop()

client = anthropic.Anthropic(api_key=api_key)

if "resultado_migracion" not in st.session_state:
    st.session_state.resultado_migracion = None

st.subheader("1. Migración de datos")
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


if st.button("Procesar migración", type="primary"):
    paths_temporales = []
    for archivo in archivos_subidos or []:
        sufijo = Path(archivo.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
            tmp.write(archivo.getvalue())
            paths_temporales.append(tmp.name)

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
        except Exception as e:
            st.exception(e)
        finally:
            for p in paths_temporales:
                os.unlink(p)

resultado = st.session_state.resultado_migracion

if resultado:
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
            with st.expander(f"{info['kpi_nombre']} — {fmt_por_unidad(info['valor'], info['unidad'])}"):
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
        st.dataframe(
            [{"Variable": v, "Valor extraído": info["valor"], "Fuente": info["fuente"], "Motivo": info["motivo"]}
             for v, info in resultado["variables_en_cuarentena"].items()],
            use_container_width=True,
        )

    if resultado.get("variables_derivadas"):
        st.subheader("2e. Variables derivadas de una tasa")
        st.caption(
            "La planilla no traía estas variables como columna, pero sí la tasa que las contiene: "
            "se despejaron algebraicamente. Se muestran siempre como dato a confirmar, nunca como "
            "valor observado."
        )
        st.dataframe(
            [{"Variable": d["variable"], "Valor derivado": d["valor"],
              "Despejada de": d["desde_denominador"], "Tasa declarada (%)": d["tasa_declarada"],
              "KPI origen": d["kpi_id"]}
             for d in resultado["variables_derivadas"]],
            use_container_width=True,
        )

    if resultado.get("discrepancias_reconciliacion"):
        st.subheader("2d. Discrepancias de reconciliación")
        st.caption("La tasa que calcula el KPI no coincide con la que la propia planilla ya declaraba al lado.")
        st.dataframe(resultado["discrepancias_reconciliacion"], use_container_width=True)

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
            "Confianza prom.",
            "—" if calidad.confianza_promedio is None else f"{calidad.confianza_promedio:.2f}",
        )
        c4.metric("En cuarentena", calidad.datos_en_cuarentena)
        if calidad.kpis_afectados:
            st.caption(f"KPIs afectados por datos en cuarentena: {calidad.kpis_afectados}")

    st.subheader("3. Preguntas pendientes del wizard")
    if resultado["preguntas_wizard"]:
        for p in resultado["preguntas_wizard"]:
            st.markdown(f"- **{p['variable']}** (desbloquea KPIs {p['kpis_que_desbloquea']}): {p['pregunta']}")
    else:
        st.caption("Ninguna — está todo cubierto.")

    st.subheader("4. Conflictos pendientes de confirmar")
    if resultado["conflictos_pendientes"]:
        for c in resultado["conflictos_pendientes"]:
            st.warning(f"**{c['variable']}**: {c['pregunta']}")
            st.json(c["opciones"])
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
        st.dataframe(
            [{
                "Score": round(o.score, 3),
                "Intervención": o.oportunidad.intervencion.nombre,
                "Tipo": o.oportunidad.intervencion.tipo,
                "Etapa": o.oportunidad.intervencion.etapa,
                "KPI": o.kpi_id,
                "Métrica objetivo": o.oportunidad.intervencion.metrica_objetivo,
                "Addressability": round(o.oportunidad.addressability, 2),
                "Condición": o.oportunidad.intervencion.condicion,
            } for o in oportunidades],
            use_container_width=True,
        )

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
