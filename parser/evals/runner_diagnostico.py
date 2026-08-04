"""
evals/runner_diagnostico.py

Fase 8 del plan de evolución: corre el motor determinista completo
(diagnostico.py -> catalogo_tecnologico.py -> priorizacion.py) contra los
casos sintéticos de casos_diagnostico.py y reporta las tres métricas que
pide esa fase del plan:

  - Precisión de cuello de botella: ¿la oportunidad con mayor score
    apunta al KPI que el caso esperaba?
  - Tasa de falsos diagnósticos: casos sin problema real (clínica sana)
    que terminan generando una oportunidad de todas formas.
  - % de recomendaciones accionables: de todas las oportunidades
    generadas, cuántas tienen addressability >= 0.6 (hay un camino de
    entrega razonable, no un requisito bloqueado).

A diferencia de evals/runner.py, esto NO llama a la API de Claude — todo
lo que evalúa acá es determinista (diagnostico.py no usa el modelo). No
reemplaza la validación real del §24 del Documento Maestro (casos reales
anonimizados + diagnóstico de un experto humano) — ver el docstring de
casos_diagnostico.py.

Uso:
    python -m parser.evals.runner_diagnostico
"""

from parser.catalogo.catalogo_tecnologico import mapear_oportunidades
from parser.diagnostico.diagnostico import diagnosticar
from parser.diagnostico.priorizacion import priorizar_oportunidades
from parser.evals import casos_diagnostico as datos

UMBRAL_ACCIONABLE = 0.6


def _correr_caso(caso: "datos.CasoDiagnostico") -> dict:
    diagnosticos = diagnosticar(caso.kpis_calculados, caso.respuestas_diagnostico)
    oportunidades = mapear_oportunidades(diagnosticos, contexto_clinica=caso.respuestas_diagnostico)
    impacto_por_kpi = {d.kpi_id: 1.0 for d in diagnosticos}
    priorizadas = priorizar_oportunidades(oportunidades, impacto_por_kpi, top_n=5)

    return {
        "diagnosticos": diagnosticos,
        "oportunidades": oportunidades,
        "priorizadas": priorizadas,
    }


def _evaluar_caso(caso: "datos.CasoDiagnostico", resultado: dict) -> list[tuple[str, bool, str]]:
    checks = []
    diagnosticos_por_kpi = {d.kpi_id: d for d in resultado["diagnosticos"]}

    if caso.cuello_de_botella_esperado is not None:
        if resultado["priorizadas"]:
            top_kpi = resultado["priorizadas"][0].kpi_id
            ok = top_kpi == caso.cuello_de_botella_esperado
            checks.append(("cuello_de_botella", ok, f"esperado={caso.cuello_de_botella_esperado} top={top_kpi}"))
        else:
            # Puede no haber oportunidades (ej. INSUFFICIENT_EVIDENCE) y
            # aun así ser correcto — se valida contra el estado, no contra
            # la ausencia de oportunidades.
            d = diagnosticos_por_kpi.get(caso.cuello_de_botella_esperado)
            ok = d is not None
            checks.append(("cuello_de_botella_sin_oportunidad", ok, f"kpi={caso.cuello_de_botella_esperado} presente={ok}"))

    if caso.estado_esperado is not None and caso.cuello_de_botella_esperado is not None:
        d = diagnosticos_por_kpi.get(caso.cuello_de_botella_esperado)
        estado_real = d.estado.value if d else None
        ok = estado_real == caso.estado_esperado
        checks.append(("estado_esperado", ok, f"esperado={caso.estado_esperado} real={estado_real}"))

    if caso.debe_tener_contradiccion:
        alguna = any(d.contradicciones for d in resultado["diagnosticos"])
        checks.append(("contradiccion_detectada", alguna, f"contradicciones encontradas={alguna}"))

    if caso.debe_tener_patron_cruzado:
        alguno = any(d.patrones_cruzados for d in resultado["diagnosticos"])
        checks.append(("patron_cruzado_detectado", alguno, f"patrones encontrados={alguno}"))

    if not caso.debe_generar_oportunidades:
        ok = len(resultado["oportunidades"]) == 0
        checks.append(("sin_falso_diagnostico", ok, f"oportunidades generadas={len(resultado['oportunidades'])}"))

    return checks


def main():
    total_checks = 0
    checks_ok = 0
    total_oportunidades = 0
    oportunidades_accionables = 0
    falsos_diagnosticos = 0
    casos_sanos = 0

    for caso in datos.CASOS:
        print(f"\n=== {caso.nombre} ===")
        print(f"  {caso.descripcion}")
        resultado = _correr_caso(caso)
        checks = _evaluar_caso(caso, resultado)

        for nombre, ok, detalle in checks:
            total_checks += 1
            checks_ok += int(ok)
            print(f"  [{'OK' if ok else 'FALLA':5}] {nombre}: {detalle}")

        if not caso.debe_generar_oportunidades:
            casos_sanos += 1
            if resultado["oportunidades"]:
                falsos_diagnosticos += 1

        for o in resultado["oportunidades"]:
            total_oportunidades += 1
            if o.addressability >= UMBRAL_ACCIONABLE:
                oportunidades_accionables += 1

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Checks: {checks_ok}/{total_checks} pasaron")
    if casos_sanos:
        print(f"Tasa de falsos diagnósticos: {falsos_diagnosticos}/{casos_sanos} casos sanos con oportunidad generada")
    if total_oportunidades:
        pct_accionables = round(100 * oportunidades_accionables / total_oportunidades, 1)
        print(f"Recomendaciones accionables (addressability >= {UMBRAL_ACCIONABLE}): "
              f"{oportunidades_accionables}/{total_oportunidades} ({pct_accionables}%)")
    else:
        print("Recomendaciones accionables: sin oportunidades generadas en ningún caso")


if __name__ == "__main__":
    main()
