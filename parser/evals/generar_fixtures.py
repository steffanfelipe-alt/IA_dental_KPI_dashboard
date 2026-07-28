"""
evals/generar_fixtures.py

Genera los archivos fixture usados por evals/runner.py y define, en el
mismo módulo, los datos crudos de los que salen — así el valor esperado
en un caso dorado nunca puede desincronizarse del archivo que lo genera
(un solo lugar define "la verdad").

Correr con `python3 generar_fixtures.py` desde parser/evals/ para
regenerar los .xlsx/.csv en fixtures/ (no hace falta correrlo salvo que
se cambien los datos de acá — los archivos generados quedan versionados).

Reproduce a propósito los patrones reales que rompían el parser:
- una hoja "Resumen mensual" con una fila TOTAL/Prom. después de los
  meses (el bug de la Fase 1.1: promediar esa fila como si fuera un mes más)
- columnas de conteo Y de tasa lado a lado para la misma variable, para
  poder detectar si el extractor toma la columna equivocada
- una hoja "Operativo" en formato "una fila = una métrica distinta", con
  unidades mezcladas (horas, %, booleano) — el trampolín que hacía que
  variables sin relación terminaran con el mismo número promediado
- una hoja "Financiero" con montos en ARS
- un CSV transaccional con una columna de categoría (tratamiento) para
  ejercitar el agrupamiento de variables tipo dict (ingreso_por_tratamiento)
"""

import os

import pandas as pd

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# ---------------------------------------------------------------------------
# Datos crudos — única fuente de verdad para los valores esperados
# ---------------------------------------------------------------------------

MESES = ["Enero 2026", "Febrero 2026", "Marzo 2026", "Abril 2026"]
CONSULTAS_NUEVAS = [95, 88, 110, 102]
TURNOS_AGENDADOS = [66, 62, 79, 73]
ASISTEN = [51, 48, 62, 57]
PRESUP_ENTREGADOS = [47, 44, 56, 52]
PRESUP_ACEPTADOS = [22, 21, 29, 27]
TRATAM_COMPLETADOS = [16, 15, 21, 19]

FACTURADO = [4650000, 4380000, 6120000, 5510000]
COBRADO = [4460000, 4200000, 5940000, 5320000]

# hoja "Operativo": una fila = una métrica, no una categoría a agrupar
TIEMPO_RESPUESTA_HORAS = 6.5
HORAS_TAREA_MANUAL_SEMANA = 21
PCT_AUTOMATIZADO = 0.05
TAREAS_SIN_BACKUP = 4

TRANSACCIONES = [
    # (tratamiento, monto_ars, estado)
    ("Conducto + corona", 199000, "pendiente"),
    ("Ortodoncia (plan completo)", 578000, "pendiente"),
    ("Ortodoncia (plan completo)", 617000, "aceptado"),
    ("Ortodoncia (plan completo)", 513000, "aceptado"),
    ("Protesis removible", 270000, "aceptado"),
    ("Limpieza + arreglos varios", 130000, "pendiente"),
    ("Extraccion + implante", 444000, "aceptado"),
    ("Ortodoncia (plan completo)", 613000, "aceptado"),
    ("Limpieza + arreglos varios", 109000, "aceptado"),
    ("Conducto + corona", 284000, "pendiente"),
    ("Conducto + corona", 273000, "aceptado"),
    ("Conducto + corona", 307000, "aceptado"),
    ("Implante unitario", 445000, "pendiente"),
    ("Conducto + corona", 248000, "aceptado"),
    ("Ortodoncia (plan completo)", 521000, "aceptado"),
]


def _no_shows(asisten, turnos):
    return [t - a for t, a in zip(turnos, asisten)]


def _tasa(numerador, denominador):
    return [n / d if d else 0.0 for n, d in zip(numerador, denominador)]


def escribir_resumen_mensual(path: str) -> None:
    no_shows = _no_shows(ASISTEN, TURNOS_AGENDADOS)
    filas = []
    for i, mes in enumerate(MESES):
        filas.append([
            mes, CONSULTAS_NUEVAS[i], TURNOS_AGENDADOS[i], ASISTEN[i],
            PRESUP_ENTREGADOS[i], PRESUP_ACEPTADOS[i], TRATAM_COMPLETADOS[i],
            TURNOS_AGENDADOS[i] / CONSULTAS_NUEVAS[i],
            no_shows[i] / TURNOS_AGENDADOS[i],
            PRESUP_ACEPTADOS[i] / PRESUP_ENTREGADOS[i],
            TRATAM_COMPLETADOS[i] / PRESUP_ACEPTADOS[i],
        ])
    total = [
        "TOTAL / Prom.", sum(CONSULTAS_NUEVAS), sum(TURNOS_AGENDADOS), sum(ASISTEN),
        sum(PRESUP_ENTREGADOS), sum(PRESUP_ACEPTADOS), sum(TRATAM_COMPLETADOS),
        sum(TURNOS_AGENDADOS) / sum(CONSULTAS_NUEVAS),
        sum(no_shows) / sum(TURNOS_AGENDADOS),
        sum(PRESUP_ACEPTADOS) / sum(PRESUP_ENTREGADOS),
        sum(TRATAM_COMPLETADOS) / sum(PRESUP_ACEPTADOS),
    ]
    columnas = ["Mes", "Consultas nuevas", "Agendan 1er turno", "Asisten",
                "Presup. entregados", "Presup. aceptados", "Tratam. completados",
                "Tasa agenda", "Tasa no-show", "Tasa aceptacion", "Tasa finalizacion"]
    encabezado_extra = [
        ["Clinica Demo — fixture de evals (no es un archivo real de clínica)"] + [None] * 10,
        ["Resumen operativo mensual - Ene a Abr 2026 (embudo de pacientes)"] + [None] * 10,
        [None] * 11,
        columnas,
    ]
    filas_totales = encabezado_extra + filas + [total]
    return pd.DataFrame(filas_totales)


def escribir_financiero(path: str) -> pd.DataFrame:
    filas = []
    for i, mes in enumerate(MESES):
        filas.append([mes, FACTURADO[i], COBRADO[i], COBRADO[i] / FACTURADO[i]])
    columnas = ["Mes", "Facturado (ARS)", "Cobrado (ARS)", "Tasa de cobro"]
    encabezado_extra = [
        ["Financiero mensual (ARS) — fixture de evals"] + [None] * 3,
        [None] * 4,
        columnas,
    ]
    return pd.DataFrame(encabezado_extra + filas)


def escribir_operativo(path: str) -> pd.DataFrame:
    filas = [
        ["Tiempo de 1ra respuesta a consulta nueva", TIEMPO_RESPUESTA_HORAS, "horas"],
        ["Horas/semana de recepcion en tareas repetitivas", HORAS_TAREA_MANUAL_SEMANA, "horas"],
        ["% de tareas repetitivas automatizadas", PCT_AUTOMATIZADO, "porcentaje"],
        ["Tareas criticas que dependen de 1 sola persona", TAREAS_SIN_BACKUP, "cantidad"],
    ]
    columnas = ["Metrica", "Valor", "Unidad"]
    encabezado_extra = [
        ["Operativo - eje de tiempo — fixture de evals"] + [None] * 2,
        [None] * 3,
        columnas,
    ]
    return pd.DataFrame(encabezado_extra + filas)


# Formato de celda por hoja y columna (0-based), como lo tendría una
# planilla real: las tasas van formateadas como porcentaje y los montos
# como moneda. pandas.to_excel escribe todo como "General", así que sin
# esto el fixture no ejercitaría la guarda de formato de excel_parser
# (_formato_incompatible) — que es justamente la defensa determinista
# contra confundir una columna de tasa con una de conteo.
FORMATOS_POR_HOJA: dict[str, dict[int, str]] = {
    # Resumen mensual: columnas 7-10 son las 4 tasas
    "Resumen mensual": {7: "0.0%", 8: "0.0%", 9: "0.0%", 10: "0.0%"},
    # Financiero: 1-2 son montos en ARS, 3 es la tasa de cobro
    "Financiero": {1: '"$"#,##0', 2: '"$"#,##0', 3: "0.0%"},
}


def _aplicar_formatos(writer) -> None:
    for hoja, formatos in FORMATOS_POR_HOJA.items():
        ws = writer.sheets[hoja]
        for idx_columna, formato in formatos.items():
            for fila in ws.iter_rows(min_col=idx_columna + 1, max_col=idx_columna + 1):
                for celda in fila:
                    if isinstance(celda.value, (int, float)):
                        celda.number_format = formato


def generar_excel_clinica() -> str:
    path = os.path.join(FIXTURES_DIR, "clinica_demo_metricas.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        escribir_resumen_mensual(path).to_excel(writer, sheet_name="Resumen mensual", header=False, index=False)
        escribir_financiero(path).to_excel(writer, sheet_name="Financiero", header=False, index=False)
        escribir_operativo(path).to_excel(writer, sheet_name="Operativo", header=False, index=False)
        _aplicar_formatos(writer)
    return path


def generar_csv_presupuestos() -> str:
    path = os.path.join(FIXTURES_DIR, "presupuestos_demo.csv")
    df = pd.DataFrame(TRANSACCIONES, columns=["tratamiento", "monto_ars", "estado"])
    df.insert(0, "fecha_presupuesto", "2026-03-01")
    df.insert(1, "id_paciente", [f"P{1000+i}" for i in range(len(df))])
    df.to_csv(path, index=False)
    return path


if __name__ == "__main__":
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    p1 = generar_excel_clinica()
    p2 = generar_csv_presupuestos()
    print(f"Generado: {p1}")
    print(f"Generado: {p2}")
