"""
test_interpretacion.py

Sin pytest, sin API real (client=None devuelve el payload crudo): corre
con `python -m parser.interpretacion.test_interpretacion`.
Cubre la Fase 4 del plan de confiabilidad: derivar semanas_de_datos_propios
de la serie real (hallazgo 4) y el panel completo (hallazgo 2). También
cubre interpretar_clinica (Fase 7): el tercer entry point que arma el
informe jerárquico a partir de diagnostico.py + catalogo_tecnologico.py +
priorizacion.py.
"""

import json

from parser.diagnostico.calidad import evaluar_calidad
from parser.vocabulario.claude_utils import extraer_texto, respuesta_truncada
from parser.catalogo.catalogo_tecnologico import mapear_oportunidades
from parser.diagnostico.diagnostico import diagnosticar
from parser.interpretacion.interpretacion import (
    SYSTEM_PROMPT_BASE, interpretar_clinica, interpretar_kpi, interpretar_panel, semanas_desde_serie,
)
from parser.diagnostico.priorizacion import priorizar_oportunidades


def test_semanas_desde_serie_vacia_es_cero():
    assert semanas_desde_serie(None) == 0
    assert semanas_desde_serie({}) == 0


def test_semanas_desde_serie_cuatro_meses():
    serie = {"Enero 2026": 1, "Febrero 2026": 2, "Marzo 2026": 3, "Abril 2026": 4}
    # 4 meses * 4.33 semanas/mes ~= 17
    assert semanas_desde_serie(serie) == 17


def test_interpretar_kpi_deriva_semanas_de_la_serie_si_no_se_pasan():
    serie = {"Enero 2026": 20, "Febrero 2026": 22, "Marzo 2026": 25}
    resultado = interpretar_kpi(4, 25, respuestas_diagnostico={}, serie_historica=serie)
    payload = resultado["payload_enviado_al_asistente"]
    assert payload["semanas_de_datos_propios"] == semanas_desde_serie(serie)
    assert payload["semanas_de_datos_propios"] > 0


def test_interpretar_kpi_respeta_semanas_explicitas_aunque_haya_serie():
    serie = {"Enero 2026": 20, "Febrero 2026": 22}
    resultado = interpretar_kpi(4, 25, respuestas_diagnostico={}, serie_historica=serie, semanas_de_datos_propios=0)
    assert resultado["payload_enviado_al_asistente"]["semanas_de_datos_propios"] == 0


def test_interpretar_kpi_incluye_valor_formateado():
    resultado = interpretar_kpi(11, 5226666.67, respuestas_diagnostico={})
    assert resultado["payload_enviado_al_asistente"]["valor_formateado"] == "$5.226.667"


def test_interpretar_panel_arma_un_kpi_por_entrada():
    kpis_calculados = {
        1: {"nombre": "Consultas nuevas / mes", "valor": 102, "unidad": "conteo", "confianza": 0.9},
        4: {"nombre": "Tasa de no-show", "valor": 21.9, "unidad": "%", "confianza": 0.9,
            "serie": {"Marzo 2026": 20.0, "Abril 2026": 21.9}},
    }
    resultado = interpretar_panel(kpis_calculados, respuestas_diagnostico={})
    payload = resultado["payload_enviado_al_asistente"]
    assert len(payload["kpis"]) == 2
    kpi4 = next(k for k in payload["kpis"] if k["kpi_id"] == 4)
    assert kpi4["gap"]["tiene_benchmark"] is True
    assert kpi4["serie_historica_propia"] == {"Marzo 2026": 20.0, "Abril 2026": 21.9}
    assert kpi4["ponderacion"]["historial"] > 0  # tiene 2 meses de serie propia, no queda en 0


def test_interpretar_panel_no_rompe_con_kpi_de_valor_dict():
    # KPI 19 y 20 devuelven un dict (no un escalar) — no debe intentar
    # calcular_gap sobre eso.
    kpis_calculados = {
        19: {"nombre": "Costo adquisición vs. reactivación",
             "valor": {"costo_adquisicion": 5000, "costo_reactivacion": 2000},
             "unidad": "$/paciente", "confianza": 0.8},
    }
    resultado = interpretar_panel(kpis_calculados, respuestas_diagnostico={})
    kpi19 = resultado["payload_enviado_al_asistente"]["kpis"][0]
    assert kpi19["gap"]["tiene_benchmark"] is False


def test_interpretar_panel_incluye_contexto_general():
    resultado = interpretar_panel({}, respuestas_diagnostico={"P44": "clínica de 3 sillones"})
    assert "P44" in resultado["payload_enviado_al_asistente"]["contexto_general"]


def test_interpretar_clinica_sin_cliente_devuelve_payload_crudo():
    kpis_calculados = {
        4: {"valor": 40.0, "serie": None},
        5: {"valor": 80.0, "serie": None},
        6: {"valor": 20000.0, "serie": None},
    }
    respuestas = {"P2": "Recordatorio automático de confirmación"}
    diagnosticos = diagnosticar(kpis_calculados, respuestas)
    oportunidades = mapear_oportunidades(diagnosticos, contexto_clinica=respuestas)
    priorizadas = priorizar_oportunidades(oportunidades, impacto_por_kpi={d.kpi_id: 1.0 for d in diagnosticos})
    calidad = evaluar_calidad({
        "kpis_calculados": kpis_calculados, "kpis_bloqueados_por_diseno": [],
        "kpis_con_error": {}, "kpis_esperando_resolucion_conflicto": {},
        "variables_en_cuarentena": {}, "discrepancias_reconciliacion": [], "variables": {},
    })

    resultado = interpretar_clinica(
        diagnosticos, priorizadas, calidad_datos=calidad,
        respuestas_diagnostico=respuestas, studio_nombre="Clínica de prueba",
    )
    assert resultado["informe"] is None
    payload = resultado["payload_enviado_al_asistente"]
    assert payload["studio_nombre"] == "Clínica de prueba"
    assert len(payload["diagnosticos"]) == 3
    assert payload["calidad_datos"]["completitud_pct"] == calidad.completitud_pct

    # El payload completo tiene que ser serializable a JSON de verdad —
    # EstadoEvidencia es str+Enum, pero hay que confirmarlo, no asumirlo.
    texto = json.dumps(payload, ensure_ascii=False, default=str)
    assert "PROBLEM" in texto or "CRITICAL" in texto or "WATCH" in texto


def test_interpretar_clinica_incluye_contradiccion_y_patron_en_el_payload():
    kpis_calculados = {4: {"valor": 40.0, "serie": None}, 5: {"valor": 80.0, "serie": None}, 6: {"valor": 20000.0, "serie": None}}
    respuestas = {"P2": "Recordatorio automático"}
    diagnosticos = diagnosticar(kpis_calculados, respuestas)
    resultado = interpretar_clinica(diagnosticos, [], respuestas_diagnostico=respuestas)
    payload = resultado["payload_enviado_al_asistente"]

    d4 = next(d for d in payload["diagnosticos"] if d["kpi_id"] == 4)
    assert len(d4["contradicciones"]) == 1

    d5 = next(d for d in payload["diagnosticos"] if d["kpi_id"] == 5)
    assert d5["patrones_cruzados"]  # el patrón de mix (KPI 5 alto + KPI 6 bajo)


def test_interpretar_clinica_incluye_oportunidades_con_intervencion_anidada():
    kpis_calculados = {4: {"valor": 40.0, "serie": None}}
    diagnosticos = diagnosticar(kpis_calculados, {})
    oportunidades = mapear_oportunidades(diagnosticos)
    priorizadas = priorizar_oportunidades(oportunidades, impacto_por_kpi={4: 1.0})

    resultado = interpretar_clinica(diagnosticos, priorizadas)
    payload = resultado["payload_enviado_al_asistente"]
    assert payload["oportunidades_priorizadas"]
    primera = payload["oportunidades_priorizadas"][0]
    assert "nombre" in primera["intervencion"]
    assert "tipo" in primera["intervencion"]


def test_interpretar_clinica_vacio_no_rompe():
    resultado = interpretar_clinica([], [])
    assert resultado["payload_enviado_al_asistente"]["diagnosticos"] == []
    assert resultado["payload_enviado_al_asistente"]["oportunidades_priorizadas"] == []
    assert resultado["payload_enviado_al_asistente"]["calidad_datos"] is None


# ---------------------------------------------------------------------------
# Fase I5: el informe pasó de ver sólo calidad_datos (4 números agregados)
# a ver también los casos puntuales — cuarentena, discrepancias, derivadas
# y conflictos — ya traducidos por explicaciones.py.
# ---------------------------------------------------------------------------

def test_interpretar_clinica_sin_los_parametros_nuevos_da_detalle_vacio():
    """Retrocompatibilidad: un llamador viejo (sin pasar los 4 params
    nuevos) sigue funcionando — calidad_datos_detalle sale con listas
    vacías, no rompe ni falta la clave."""
    resultado = interpretar_clinica([], [])
    detalle = resultado["payload_enviado_al_asistente"]["calidad_datos_detalle"]
    assert detalle == {
        "variables_en_cuarentena": [], "discrepancias_reconciliacion": [],
        "variables_derivadas": [], "conflictos_pendientes": [],
    }


def test_interpretar_clinica_humaniza_la_cuarentena():
    resultado = interpretar_clinica(
        [], [],
        variables_en_cuarentena={
            "no_shows": {"valor": "cuarenta", "fuente": "migracion_excel", "motivo": "se esperaba número, llegó str"},
        },
    )
    detalle = resultado["payload_enviado_al_asistente"]["calidad_datos_detalle"]
    assert len(detalle["variables_en_cuarentena"]) == 1
    assert "tiene que ser un número" in detalle["variables_en_cuarentena"][0]["explicacion"]


def test_interpretar_clinica_marca_cuarentena_ya_resuelta_en_vez_de_ocultarla():
    """No excluirla del todo: si el agregado calidad_datos.datos_en_cuarentena
    la sigue contando (calidad.py no mira reemplazada_por_derivacion) y acá
    se la sacara entera, el modelo ve "1 en cuarentena" en el agregado y
    una lista vacía en el detalle, sin poder explicar la diferencia — pasó
    en una corrida real antes de este fix."""
    resultado = interpretar_clinica(
        [], [],
        variables_en_cuarentena={
            "no_shows": {
                "valor": "x", "fuente": "y", "motivo": "algo — reemplazada por un valor derivado de la tasa",
                "reemplazada_por_derivacion": True,
            },
        },
    )
    detalle = resultado["payload_enviado_al_asistente"]["calidad_datos_detalle"]
    assert len(detalle["variables_en_cuarentena"]) == 1
    assert detalle["variables_en_cuarentena"][0]["resuelta"] is True


def test_interpretar_clinica_cuarentena_sin_resolver_marca_resuelta_false():
    resultado = interpretar_clinica(
        [], [],
        variables_en_cuarentena={
            "no_shows": {"valor": "cuarenta", "fuente": "migracion_excel", "motivo": "se esperaba número, llegó str"},
        },
    )
    detalle = resultado["payload_enviado_al_asistente"]["calidad_datos_detalle"]
    assert detalle["variables_en_cuarentena"][0]["resuelta"] is False


def test_interpretar_clinica_conflictos_excluye_identidad_paciente():
    resultado = interpretar_clinica(
        [], [],
        conflictos_pendientes=[
            {"variable": "no_shows", "tipo": "valores_distintos", "pregunta": "¿Cuál es correcto?"},
            {"variable": "identidad_paciente", "pregunta": "¿Es la misma persona?"},
        ],
    )
    detalle = resultado["payload_enviado_al_asistente"]["calidad_datos_detalle"]
    assert len(detalle["conflictos_pendientes"]) == 1
    assert detalle["conflictos_pendientes"][0]["variable"] == "no_shows"


def test_interpretar_clinica_oportunidad_incluye_beneficio_y_plazo():
    kpis_calculados = {4: {"valor": 40.0, "serie": None}}
    diagnosticos = diagnosticar(kpis_calculados, {})
    oportunidades = mapear_oportunidades(diagnosticos)
    priorizadas = priorizar_oportunidades(oportunidades, impacto_por_kpi={4: 1.0})

    resultado = interpretar_clinica(diagnosticos, priorizadas)
    primera = resultado["payload_enviado_al_asistente"]["oportunidades_priorizadas"][0]
    assert "beneficio" in primera["intervencion"]
    assert "periodo_evaluacion_semanas" in primera["intervencion"]
    assert primera["intervencion"]["beneficio"]  # no vacío para ninguna de las 35


# ---------------------------------------------------------------------------
# Truncamiento: el modo de falla silencioso (informe cortado que se ve
# completo) es peor que el ruidoso. Bug real — las tres llamadas omitían
# `thinking`, que en los modelos actuales significa adaptativo, no "sin
# thinking": el presupuesto se iba entero en pensar y no quedaba texto.
# ---------------------------------------------------------------------------

class _Bloque:
    def __init__(self, tipo, texto=""):
        self.type, self.text = tipo, texto


class _Respuesta:
    def __init__(self, content, stop_reason):
        self.content, self.stop_reason = content, stop_reason


def test_respuesta_sin_texto_por_max_tokens_explica_la_causa():
    respuesta = _Respuesta([_Bloque("thinking")], "max_tokens")
    assert respuesta_truncada(respuesta)
    try:
        extraer_texto(respuesta)
    except ValueError as e:
        assert "thinking" in str(e), "el error debe nombrar la causa, no solo el síntoma"
    else:
        raise AssertionError("debía fallar: no hay bloque de texto")


def test_texto_parcial_por_max_tokens_queda_marcado_como_truncado():
    """El caso peligroso: SÍ hay texto, así que extraer_texto lo devuelve.
    Sin la marca, media sección se mostraba como informe terminado."""
    respuesta = _Respuesta([_Bloque("text", "## 1. RESUMEN EJECUTIVO\nLa clínica pre")], "max_tokens")
    assert extraer_texto(respuesta).startswith("## 1.")
    assert respuesta_truncada(respuesta) is True


def test_respuesta_completa_no_se_marca_truncada():
    respuesta = _Respuesta([_Bloque("text", "informe completo")], "end_turn")
    assert respuesta_truncada(respuesta) is False


def test_los_tres_entry_points_declaran_truncado_sin_cliente():
    assert interpretar_kpi(3, 50.0, {}, puerto=None)["truncado"] is False
    assert interpretar_panel({}, {}, puerto=None)["truncado"] is False
    assert interpretar_clinica([], [], client=None)["truncado"] is False


# ---------------------------------------------------------------------------
# deuda-panel-sistemas-puertollm (U1): interpretar_kpi/interpretar_panel
# pasaron de un `client` crudo de Anthropic a `puerto: Optional[PuertoLLM]`,
# hablando contra `preguntar_con_truncamiento` en vez de
# `client.messages.create(...)` + `respuesta_truncada(respuesta)` a mano.
# Antes de este cambio, la rama `client is not None` de ambas funciones no
# tenía NINGUNA cobertura — este bloque cierra ese gap, incluyendo el caso
# de truncamiento (el que antes motivó declarar `thinking` explícito).
# `interpretar_clinica` sigue con `client`/streaming crudo a propósito, no
# se toca acá.
# ---------------------------------------------------------------------------

class _PuertoLLMFalso:
    """Fake del Protocol `PuertoLLM`: `preguntar_con_truncamiento` devuelve
    directamente el par (texto, truncado) configurado, sin pasar por
    `anthropic.Anthropic` ni por `client.messages.create`. Mismo patrón que
    `_PuertoLLMFalso` en `parser/extraccion/test_*.py`, extendido con el
    segundo método que agregó U1."""

    def __init__(self, texto: str, truncado: bool = False):
        self._texto = texto
        self._truncado = truncado
        self.ultima_llamada = None
        self.llamadas = 0

    def preguntar_con_truncamiento(self, **kwargs):
        self.ultima_llamada = kwargs
        self.llamadas += 1
        return self._texto, self._truncado


def test_interpretar_kpi_con_puerto_devuelve_interpretacion_del_puerto():
    puerto = _PuertoLLMFalso("gap moderado, seguir observando")
    resultado = interpretar_kpi(4, 25.0, respuestas_diagnostico={}, puerto=puerto)
    assert resultado["interpretacion"] == "gap moderado, seguir observando"
    assert resultado["truncado"] is False
    assert puerto.llamadas == 1
    assert puerto.ultima_llamada["system"] == SYSTEM_PROMPT_BASE


def test_interpretar_kpi_con_puerto_truncado_propaga_truncado_true():
    puerto = _PuertoLLMFalso("## interpretación cortada a la mit", truncado=True)
    resultado = interpretar_kpi(4, 25.0, respuestas_diagnostico={}, puerto=puerto)
    assert resultado["truncado"] is True
    assert resultado["interpretacion"] == "## interpretación cortada a la mit"


def test_interpretar_panel_con_puerto_devuelve_interpretacion_del_puerto():
    puerto = _PuertoLLMFalso("panel completo: mix de tratamientos explica la brecha")
    kpis_calculados = {4: {"valor": 21.9, "unidad": "%", "confianza": 0.9}}
    resultado = interpretar_panel(kpis_calculados, respuestas_diagnostico={}, puerto=puerto)
    assert resultado["interpretacion"] == "panel completo: mix de tratamientos explica la brecha"
    assert resultado["truncado"] is False
    assert puerto.llamadas == 1


def test_interpretar_panel_con_puerto_truncado_propaga_truncado_true():
    puerto = _PuertoLLMFalso("panel cortado a la mit", truncado=True)
    resultado = interpretar_panel({}, respuestas_diagnostico={}, puerto=puerto)
    assert resultado["truncado"] is True
    assert resultado["interpretacion"] == "panel cortado a la mit"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
