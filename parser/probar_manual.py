"""
probar_manual.py

Runner visual (Streamlit) para probar pipeline.procesar_migracion e
interpretacion.interpretar_kpi contra archivos reales y la API real de
Claude, sin necesitar FastAPI, frontend ni Supabase todavía.

Correr desde agencia_ia_dental_dashboard/:
    source venv/bin/activate
    streamlit run parser/probar_manual.py

Necesita ANTHROPIC_API_KEY en el entorno o en un .env en la raíz del
proyecto — nunca hardcodeada acá.
"""

import json
import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from pipeline import EXTRACTOR_POR_EXTENSION, procesar_migracion
from interpretacion import interpretar_kpi

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

if st.button("Procesar migración", type="primary"):
    paths_temporales = []
    for archivo in archivos_subidos or []:
        sufijo = Path(archivo.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
            tmp.write(archivo.getvalue())
            paths_temporales.append(tmp.name)

    with st.spinner("Corriendo procesar_migracion contra la API real..."):
        try:
            st.session_state.resultado_migracion = procesar_migracion(paths_temporales, client=client)
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
                "Valor": info["valor"] if not isinstance(info["valor"], dict)
                else json.dumps(info["valor"], ensure_ascii=False),
                "Unidad": info["unidad"],
                "Confianza": info["confianza"],
                "Fuentes": ", ".join(info["fuentes"]),
            }
            for info in resultado["kpis_calculados"].values()
        ]
        st.dataframe(filas, use_container_width=True)
    else:
        st.caption("Ninguno todavía — depende de qué variables falten.")

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
    st.subheader("6. Interpretar un KPI calculado")
    if resultado["kpis_calculados"]:
        kpi_ids = list(resultado["kpis_calculados"].keys())
        kpi_elegido = st.selectbox(
            "KPI a interpretar",
            kpi_ids,
            format_func=lambda kid: resultado["kpis_calculados"][kid]["kpi_nombre"],
        )
        respuestas_raw = st.text_area(
            "Contexto cualitativo (opcional) — una línea por respuesta, "
            "formato 'P20: no hacemos seguimiento de presupuestos'",
            height=100,
        )
        semanas_propias = st.number_input("Semanas de datos propios de la clínica", min_value=0, value=0)

        if st.button("Interpretar"):
            respuestas = {}
            for linea in respuestas_raw.splitlines():
                if ":" in linea:
                    clave, valor = linea.split(":", 1)
                    respuestas[clave.strip()] = valor.strip()

            with st.spinner("Llamando a interpretar_kpi contra la API real..."):
                resultado_interp = interpretar_kpi(
                    kpi_id=kpi_elegido,
                    valor_clinica=resultado["kpis_calculados"][kpi_elegido]["valor"],
                    respuestas_diagnostico=respuestas,
                    semanas_de_datos_propios=int(semanas_propias),
                    client=client,
                )
            st.markdown("**Diagnóstico del asistente:**")
            st.write(resultado_interp["interpretacion"])
            with st.expander("Ver payload enviado al asistente"):
                st.json(resultado_interp["payload_enviado_al_asistente"])
    else:
        st.caption("Todavía no hay ningún KPI calculado para interpretar.")
