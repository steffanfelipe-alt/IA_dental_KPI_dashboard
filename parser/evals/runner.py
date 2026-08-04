"""
evals/runner.py

Corre el pipeline real (con la API de Claude) contra los fixtures de
evals/fixtures/ y compara el resultado con los valores de casos_dorados.py.

A diferencia de test_*.py (deterministas, sin red), esto SÍ llama a la API
— hace falta ANTHROPIC_API_KEY en el entorno o en .env. No es una suite
de pass/fail estricta porque la extracción depende de un LLM: es un
reporte de qué tan cerca está el sistema completo (extracción +
validación + reconciliación) del valor correcto, y sirve para medir
progreso fase a fase del plan de confiabilidad.

Uso:
    python -m parser.evals.runner            # una corrida
    python -m parser.evals.runner --repetir 5   # corre 5 veces, mide determinismo también
"""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from parser.evals import casos_dorados as dorado

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
XLSX = str(FIXTURES_DIR / "clinica_demo_metricas.xlsx")
CSV = str(FIXTURES_DIR / "presupuestos_demo.csv")

TOLERANCIA_PCT = 0.5  # % de tolerancia para comparar floats


def _cerca(a, b, tolerancia_pct=TOLERANCIA_PCT) -> bool:
    if a is None or b is None:
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_cerca(a[k], b[k], tolerancia_pct) for k in a)
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return a == b
    if b == 0:
        return abs(a) < 1e-6
    return abs(a - b) / abs(b) * 100 <= tolerancia_pct


def _correr_una_vez(client) -> dict:
    from parser.pipeline import procesar_migracion
    return procesar_migracion([XLSX, CSV], client=client)


def _reportar_variables(resultado: dict) -> list[tuple[str, bool, str]]:
    filas = []
    variables = resultado["variables"]
    cuarentena = resultado.get("variables_en_cuarentena", {})

    for var, esperado in dorado.VARIABLES_ESPERADAS_VIGENTE.items():
        if var in variables:
            obtenido = variables[var].valor
            ok = _cerca(obtenido, esperado)
            marca = " [DERIVADA]" if variables[var].fuente == "derivado_de_tasa" else ""
            detalle = f"obtenido={obtenido!r} esperado={esperado!r}{marca}"
        elif var in cuarentena:
            ok = False
            detalle = f"en cuarentena: {cuarentena[var]['motivo']}"
        else:
            ok = False
            detalle = "no se extrajo (ausente)"
        filas.append((var, ok, detalle))

    # Trampa: no_shows no debe terminar siendo la tasa (0.219...) en vez
    # del conteo (16).
    if "no_shows" in variables:
        valor = variables["no_shows"].valor
        confundido = isinstance(valor, (int, float)) and _cerca(valor, dorado.TASA_NO_SHOW_VIGENTE, 5)
        filas.append((
            "no_shows (trampa tasa-vs-conteo)",
            not confundido,
            f"valor={valor!r} (tasa real sería {dorado.TASA_NO_SHOW_VIGENTE:.4f})",
        ))

    if "ingreso_por_tratamiento" in variables:
        obtenido = variables["ingreso_por_tratamiento"].valor
        ok = _cerca(obtenido, dorado.INGRESO_POR_TRATAMIENTO_ESPERADO)
        filas.append(("ingreso_por_tratamiento", ok, f"obtenido={obtenido!r}"))
    elif "ingreso_por_tratamiento" in cuarentena:
        filas.append(("ingreso_por_tratamiento", False, f"en cuarentena: {cuarentena['ingreso_por_tratamiento']['motivo']}"))
    else:
        filas.append(("ingreso_por_tratamiento", False, "no se extrajo (ausente)"))

    return filas


def _reportar_kpis(resultado: dict) -> list[tuple[str, bool, str]]:
    filas = []
    calculados = resultado["kpis_calculados"]
    for kpi_id, esperado in dorado.KPIS_ESPERADOS_VIGENTE.items():
        if kpi_id in calculados:
            obtenido = calculados[kpi_id]["valor"]
            ok = _cerca(obtenido, esperado)
            detalle = f"obtenido={obtenido!r} esperado={esperado!r}"
        elif kpi_id in resultado.get("kpis_con_error", {}):
            ok = False
            detalle = f"error: {resultado['kpis_con_error'][kpi_id]}"
        else:
            ok = False
            detalle = "no calculado (variables faltantes o en cuarentena)"
        nombre = dorado.KPIS_ESPERADOS_VIGENTE and f"KPI {kpi_id}"
        filas.append((nombre, ok, detalle))
    return filas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetir", type=int, default=1)
    args = parser.parse_args()

    load_dotenv(str(Path(__file__).resolve().parent.parent.parent / ".env"))
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    resultados_por_variable: dict[str, list[bool]] = {}
    for intento in range(1, args.repetir + 1):
        print(f"\n=== Corrida {intento}/{args.repetir} ===")
        resultado = _correr_una_vez(client)

        print("\n-- Variables --")
        for nombre, ok, detalle in _reportar_variables(resultado):
            print(f"  [{'OK' if ok else 'FALLA':5}] {nombre:45} {detalle}")
            resultados_por_variable.setdefault(nombre, []).append(ok)

        print("\n-- KPIs --")
        for nombre, ok, detalle in _reportar_kpis(resultado):
            print(f"  [{'OK' if ok else 'FALLA':5}] {nombre:10} {detalle}")

        if resultado.get("variables_en_cuarentena"):
            print("\n-- En cuarentena --")
            for var, info in resultado["variables_en_cuarentena"].items():
                print(f"  {var}: {info['motivo']}")

        if resultado.get("variables_derivadas"):
            print("\n-- Derivadas de una tasa declarada --")
            for d in resultado["variables_derivadas"]:
                print(f"  {d['variable']} = {d['valor']} (despejada de {d['desde_denominador']} "
                      f"× {d['tasa_declarada']}%, KPI {d['kpi_id']})")

        if resultado.get("discrepancias_reconciliacion"):
            print("\n-- Discrepancias de reconciliación --")
            for d in resultado["discrepancias_reconciliacion"]:
                print(f"  KPI {d['kpi_id']} ({d['kpi_nombre']}): calculado={d['calculado']} declarado={d['declarado']} variables={d['variables']}")

    if args.repetir > 1:
        print("\n=== Determinismo ===")
        for nombre, oks in resultados_por_variable.items():
            estable = len(set(oks)) == 1
            print(f"  [{'ESTABLE' if estable else 'VARIA':8}] {nombre}: {oks}")


if __name__ == "__main__":
    main()
