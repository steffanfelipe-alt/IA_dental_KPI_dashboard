"""
test_priorizacion_extendida.py

Sin pytest: corre con `python -m parser.diagnostico.test_priorizacion_extendida`.
Cubre la Fase 6 del plan de evolución: los factores nuevos de
calcular_score (addressability, suficiencia) y el cableado completo
diagnostico.py -> catalogo_tecnologico.py -> priorizacion.py, que antes
de esta fase no llamaba nadie en producción.
"""

from parser.diagnostico.benchmarks import calcular_gap
from parser.catalogo.catalogo_tecnologico import mapear_oportunidades
from parser.diagnostico.diagnostico import Diagnostico, EstadoEvidencia, diagnosticar
from parser.diagnostico.priorizacion import calcular_score, calcular_score_diagnostico, priorizar_oportunidades


def test_addressability_baja_reduce_el_score():
    gap = calcular_gap(4, 40.0)  # KPI 4, gap grande, consultora_ar
    score_full = calcular_score(gap, impacto=1.0)
    score_con_baja_addressability = calcular_score(gap, impacto=1.0, addressability=0.3)
    assert score_con_baja_addressability < score_full
    assert score_con_baja_addressability == round(score_full * 0.3, 4)


def test_suficiencia_baja_reduce_el_score():
    gap = calcular_gap(4, 40.0)
    score_full = calcular_score(gap, impacto=1.0)
    score_con_baja_suficiencia = calcular_score(gap, impacto=1.0, suficiencia=0.5)
    assert score_con_baja_suficiencia == round(score_full * 0.5, 4)


def test_defaults_no_cambian_el_score_de_antes():
    gap = calcular_gap(4, 40.0)
    assert calcular_score(gap, impacto=2.0) == calcular_score(gap, impacto=2.0, addressability=1.0, suficiencia=1.0)


def test_calcular_score_diagnostico_healthy_da_cero():
    d = Diagnostico(
        kpi_id=4, problema="x", estado=EstadoEvidencia.HEALTHY, hechos=[], anomalias=[],
        hipotesis=[], contradicciones=[], patrones_cruzados=[], informacion_faltante=[], confianza=1.0,
    )
    assert calcular_score_diagnostico(d, impacto=10.0) == 0.0


def test_calcular_score_diagnostico_usa_confianza_como_suficiencia():
    diagnosticos = diagnosticar({4: {"valor": 40.0, "serie": None}}, {})
    d = diagnosticos[0]
    assert d.confianza == 1.0  # sin variables pasadas, se asume observado
    score_confianza_alta = calcular_score_diagnostico(d, impacto=1.0)

    d_baja_confianza = Diagnostico(**{**d.__dict__, "confianza": 0.5})
    score_confianza_baja = calcular_score_diagnostico(d_baja_confianza, impacto=1.0)
    assert score_confianza_baja == round(score_confianza_alta * 0.5, 4)


def test_priorizar_oportunidades_cablea_diagnostico_y_catalogo():
    # Cuello grande y confiable (KPI 4) vs. uno más chico (KPI 5 dentro de
    # rango => ni siquiera genera Anomalia) — el primero debería ganar.
    kpis_calculados = {4: {"valor": 40.0, "serie": None}, 5: {"valor": 70.0, "serie": None}}
    diagnosticos = diagnosticar(kpis_calculados, {})
    oportunidades = mapear_oportunidades(diagnosticos)
    assert oportunidades, "KPI 4 en CRITICAL debería generar oportunidades del catálogo"

    priorizadas = priorizar_oportunidades(oportunidades, impacto_por_kpi={4: 1.0, 5: 1.0})
    assert priorizadas[0].kpi_id == 4
    assert priorizadas[0].score > 0


def test_priorizar_oportunidades_respeta_top_n():
    kpis_calculados = {4: {"valor": 40.0, "serie": None}}
    diagnosticos = diagnosticar(kpis_calculados, {})
    oportunidades = mapear_oportunidades(diagnosticos)
    priorizadas = priorizar_oportunidades(oportunidades, impacto_por_kpi={4: 1.0}, top_n=2)
    assert len(priorizadas) <= 2


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
