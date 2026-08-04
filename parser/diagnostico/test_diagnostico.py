"""
test_diagnostico.py

Sin pytest: corre con `python -m parser.diagnostico.test_diagnostico`.
Cubre diagnostico.py (Fase 4, Diagnostic Engine): estados de evidencia,
patrones cruzados entre KPIs, y contradicciones — las tres reglas que
antes solo vivían como prosa en interpretacion.SYSTEM_PROMPT_BASE.
"""

from parser.diagnostico.benchmarks import calcular_gap
from parser.cobertura_calidad.coverage import VariableValue
from parser.diagnostico.diagnostico import (
    EstadoEvidencia,
    detectar_contradicciones,
    detectar_patrones_cruzados,
    diagnosticar,
    evaluar_estado,
)


# ---------------------------------------------------------------------------
# evaluar_estado
# ---------------------------------------------------------------------------

def test_sin_benchmark_y_sin_serie_da_insufficient_evidence_nunca_problem():
    gap = calcular_gap(7, 55.0)  # KPI 7: sin_benchmark
    assert gap.tiene_benchmark is False
    estado = evaluar_estado(gap, suficiencia=1.0, tiene_serie=False)
    assert estado == EstadoEvidencia.INSUFFICIENT_EVIDENCE


def test_sin_benchmark_pero_con_serie_da_watch_no_mas():
    gap = calcular_gap(7, 55.0)
    estado = evaluar_estado(gap, tiene_serie=True)
    assert estado == EstadoEvidencia.WATCH


def test_dentro_de_rango_es_healthy():
    gap = calcular_gap(4, 12.0)  # KPI 4: rango 8-15
    assert evaluar_estado(gap) == EstadoEvidencia.HEALTHY


def test_gap_grande_con_benchmark_confiable_es_critical():
    gap = calcular_gap(4, 40.0)  # muy por encima de 8-15, consultora_ar (confiable)
    assert evaluar_estado(gap, suficiencia=1.0) == EstadoEvidencia.CRITICAL


def test_baja_suficiencia_nunca_llega_a_critical_aunque_el_gap_sea_grande():
    gap = calcular_gap(4, 40.0)
    estado = evaluar_estado(gap, suficiencia=0.5)
    assert estado != EstadoEvidencia.CRITICAL
    assert estado == EstadoEvidencia.PROBLEM


def test_gap_chico_es_watch_no_problem():
    gap = calcular_gap(5, 64.0)  # apenas por debajo de 65 (rango 65-75, punto medio 70) -> magnitud ~8.6%
    assert gap.magnitud_pct < 20
    assert evaluar_estado(gap, suficiencia=1.0) == EstadoEvidencia.WATCH


def test_proxy_internacional_no_llega_a_critical_aunque_el_gap_sea_grande():
    # KPI 3 (agendamiento, mejor_es="mayor"): un valor muy por DEBAJO del
    # rango es el caso desfavorable real (agendamiento bajo es malo).
    gap = calcular_gap(3, 5.0)  # rango 35-50, proxy_internacional
    assert gap.favorable is False
    assert gap.magnitud_pct >= 50  # gap enorme...
    assert gap.benchmark.confiabilidad == "proxy_internacional"  # ...pero proxy, no oficial/consultora
    assert evaluar_estado(gap, suficiencia=1.0) == EstadoEvidencia.PROBLEM  # nunca CRITICAL sin benchmark firme


# ---------------------------------------------------------------------------
# Patrones cruzados
# ---------------------------------------------------------------------------

def test_aceptacion_alta_y_ticket_bajo_da_patron_de_mix():
    gaps = {5: calcular_gap(5, 80.0), 6: calcular_gap(6, 20000.0)}  # rango 65-75 / rango ~44692-89385 ARS
    patrones = detectar_patrones_cruzados(gaps)
    assert len(patrones) == 1
    assert patrones[0]["kpis_involucrados"] == (5, 6)
    assert "mix" in patrones[0]["conclusion"].lower()


def test_sin_el_patron_no_se_reporta_nada():
    gaps = {5: calcular_gap(5, 70.0), 6: calcular_gap(6, 60000.0)}  # ambos dentro de rango
    assert detectar_patrones_cruzados(gaps) == []


def test_agendamiento_alto_y_no_show_alto_da_patron_de_compromiso():
    gaps = {3: calcular_gap(3, 90.0), 4: calcular_gap(4, 30.0)}
    patrones = detectar_patrones_cruzados(gaps)
    assert any(p["kpis_involucrados"] == (3, 4) for p in patrones)


def test_produccion_baja_con_ocupacion_alta_necesita_variables():
    gaps = {12: calcular_gap(12, 100.0)}  # KPI 12 no tiene rango numérico -> tiene_benchmark=False
    assert detectar_patrones_cruzados(gaps) == []
    assert detectar_patrones_cruzados(gaps, variables={}) == []


# ---------------------------------------------------------------------------
# Contradicciones
# ---------------------------------------------------------------------------

def test_confirma_automatico_y_no_show_alto_da_contradiccion():
    gaps = {4: calcular_gap(4, 30.0)}  # bien por encima de 8-15, desfavorable
    respuestas = {"P2": "Sí, mandamos un recordatorio automático 48hs y 24hs antes"}
    contradicciones = detectar_contradicciones(gaps, respuestas)
    assert len(contradicciones) == 1
    assert contradicciones[0].kpi_id == 4
    assert "P2" in contradicciones[0].preguntas_involucradas


def test_sin_confirmacion_automatica_no_hay_contradiccion():
    gaps = {4: calcular_gap(4, 30.0)}
    respuestas = {"P2": "Lo hacemos a mano, llamamos un día antes"}
    assert detectar_contradicciones(gaps, respuestas) == []


def test_no_show_alto_pero_favorable_no_genera_contradiccion_aunque_declare_automatico():
    # no-show DEBAJO de rango (favorable, KPI4 mejor_es=menor) no es un
    # problema — no tiene sentido contradecir algo que no está mal.
    gaps = {4: calcular_gap(4, 5.0)}
    respuestas = {"P2": "Recordatorio automático"}
    assert detectar_contradicciones(gaps, respuestas) == []


# ---------------------------------------------------------------------------
# diagnosticar() — integración
# ---------------------------------------------------------------------------

def test_diagnosticar_produce_contradiccion_y_no_solo_una_anomalia_generica():
    kpis_calculados = {4: {"valor": 30.0, "serie": None}}
    respuestas = {"P2": "Recordatorio automático de confirmación"}
    diagnosticos = diagnosticar(kpis_calculados, respuestas)
    assert len(diagnosticos) == 1
    d = diagnosticos[0]
    assert d.kpi_id == 4
    assert d.estado in (EstadoEvidencia.PROBLEM, EstadoEvidencia.CRITICAL)
    assert len(d.contradicciones) == 1
    # No recomienda "agregar recordatorios" (ya existen) — señala que el
    # problema real es otro, tal como pide el §20 del Documento Maestro.
    assert "no es falta de recordatorio" in d.contradicciones[0].descripcion


def test_diagnosticar_marca_insufficient_evidence_sin_inventar_causa():
    kpis_calculados = {7: {"valor": 55.0, "serie": None}}
    diagnosticos = diagnosticar(kpis_calculados, {})
    assert diagnosticos[0].estado == EstadoEvidencia.INSUFFICIENT_EVIDENCE
    assert diagnosticos[0].informacion_faltante  # no queda vacío: dice que falta evidencia
    assert diagnosticos[0].hipotesis == []  # no inventa una causa sin evidencia


def test_diagnosticar_incluye_patrones_cruzados_del_kpi_correspondiente():
    kpis_calculados = {5: {"valor": 80.0, "serie": None}, 6: {"valor": 20000.0, "serie": None}}
    diagnosticos = diagnosticar(kpis_calculados, {})
    por_id = {d.kpi_id: d for d in diagnosticos}
    assert por_id[5].patrones_cruzados
    assert por_id[6].patrones_cruzados
    assert por_id[5].patrones_cruzados == por_id[6].patrones_cruzados


def test_diagnosticar_usa_suficiencia_de_datos_si_se_pasan_variables():
    from parser.cobertura_calidad.reconciliacion import FUENTE_DERIVADA
    kpis_calculados = {4: {"valor": 40.0, "serie": None}}
    variables = {
        "no_shows": VariableValue(16, FUENTE_DERIVADA, 0.6),
        "turnos_agendados": VariableValue(73, "migracion_excel", 0.9),
    }
    diagnosticos = diagnosticar(kpis_calculados, {}, variables=variables)
    d = diagnosticos[0]
    assert d.confianza == 0.5  # 1 de 2 variables observada
    assert d.estado != EstadoEvidencia.CRITICAL  # la derivación capea la severidad


def test_diagnosticar_sin_kpis_calculados_no_rompe():
    assert diagnosticar({}, {}) == []


# ---------------------------------------------------------------------------
# Fase G6: estacionalidad.py cableado — señal determinista de temporada en
# vez de depender de que el modelo aplique la regla desde P51 en texto
# libre. Puramente aditivo: una Hipotesis más, nunca cambia `estado`.
# ---------------------------------------------------------------------------

def test_con_p51_respondida_y_anomalia_en_temporada_aparece_hipotesis_estacional():
    kpis_calculados = {4: {"valor": 30.0, "serie": {"2025-12": 20.0, "2026-01": 30.0}}}
    respuestas = {"P51": "En enero se complica todo por la temporada turística."}
    d = diagnosticar(kpis_calculados, respuestas)[0]
    assert any("estacionalidad" in h.causa_probable or "temporada" in h.causa_probable for h in d.hipotesis)
    assert any(h.preguntas_que_la_sustentan == ["P51"] for h in d.hipotesis)


def test_sin_p51_no_aparece_hipotesis_estacional():
    kpis_calculados = {4: {"valor": 30.0, "serie": {"2025-12": 20.0, "2026-01": 30.0}}}
    d = diagnosticar(kpis_calculados, {})[0]
    assert not any("temporada" in h.causa_probable for h in d.hipotesis)


def test_fuera_de_temporada_no_aparece_hipotesis_estacional():
    # Junio no está en MESES_TEMPORADA_ALTA (verano: 01/02/12).
    kpis_calculados = {4: {"valor": 30.0, "serie": {"2026-05": 20.0, "2026-06": 30.0}}}
    respuestas = {"P51": "En enero se complica todo por la temporada turística."}
    d = diagnosticar(kpis_calculados, respuestas)[0]
    assert not any("temporada" in h.causa_probable for h in d.hipotesis)


def test_kpi_fuera_de_la_lista_no_recibe_hipotesis_estacional():
    # KPI 2 (tiempo de 1ª respuesta) no es 4 ni 12 — aunque haya anomalía
    # y P51 esté respondida para un mes de temporada, no aplica.
    kpis_calculados = {2: {"valor": 390.0, "serie": {"2025-12": 300.0, "2026-01": 390.0}}}
    respuestas = {"P51": "En enero se complica todo por la temporada turística."}
    d = diagnosticar(kpis_calculados, respuestas)[0]
    assert not any("temporada" in h.causa_probable for h in d.hipotesis)


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
