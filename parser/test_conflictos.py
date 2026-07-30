"""
test_conflictos.py

Sin pytest (no está instalado en el entorno): corre con `python3 test_conflictos.py`.
Casos del plan "resolución de conflictos de variables migradas".
"""

from coverage import VariableValue
from conflictos import resolver_conflictos, UMBRAL_EMPATE


def test_valores_iguales_no_generan_conflicto():
    fuentes = [
        {"no_shows": VariableValue(13, "migracion_excel", 0.8, archivo_origen="turnos.xlsx")},
        {"no_shows": VariableValue(13, "migracion_foto", 0.5, archivo_origen="cuaderno.jpg")},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["no_shows"].valor == 13


def test_confianza_bien_distinta_resuelve_automatico():
    fuentes = [
        {"no_shows": VariableValue(13, "migracion_excel", 0.9, archivo_origen="turnos.xlsx")},
        {"no_shows": VariableValue(20, "migracion_foto", 0.5, archivo_origen="cuaderno.jpg")},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["no_shows"].valor == 13
    assert resueltas["no_shows"].fuente == "migracion_excel"


def test_confianza_empatada_genera_conflicto_real():
    fuentes = [
        {"no_shows": VariableValue(56, "migracion_excel", 0.8, archivo_origen="turnos.xlsx")},
        {"no_shows": VariableValue(60, "migracion_foto", 0.75, archivo_origen="cuaderno.jpg")},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert "no_shows" not in resueltas
    assert len(conflictos) == 1
    conflicto = conflictos[0]
    assert conflicto.variable == "no_shows"
    valores = {c["valor"] for c in conflicto.candidatos}
    assert valores == {56, 60}
    archivos = {c["archivo"] for c in conflicto.candidatos}
    assert archivos == {"turnos.xlsx", "cuaderno.jpg"}


def test_diferencia_justo_en_el_umbral_no_es_conflicto():
    # 0.9 - 0.8 == UMBRAL_EMPATE (0.1): "diferencia >= UMBRAL_EMPATE" resuelve automático.
    fuentes = [
        {"no_shows": VariableValue(13, "migracion_excel", 0.9)},
        {"no_shows": VariableValue(20, "migracion_foto", 0.8)},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["no_shows"].valor == 13
    assert UMBRAL_EMPATE == 0.1


def test_confirmado_por_dueno_gana_siempre():
    fuentes = [
        {"no_shows": VariableValue(56, "confirmado_por_dueno", 1.0)},
        {"no_shows": VariableValue(99, "migracion_excel", 1.0, archivo_origen="turnos_nuevo.xlsx")},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["no_shows"].valor == 56
    assert resueltas["no_shows"].fuente == "confirmado_por_dueno"


def test_tercer_candidato_de_baja_confianza_no_rompe_acuerdo_entre_los_dos_mejores():
    fuentes = [
        {"no_shows": VariableValue(13, "migracion_excel", 0.9, archivo_origen="turnos.xlsx")},
        {"no_shows": VariableValue(13, "migracion_foto", 0.9, archivo_origen="cuaderno.jpg")},
        {"no_shows": VariableValue(99, "migracion_foto", 0.3, archivo_origen="foto_borrosa.jpg")},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["no_shows"].valor == 13


def test_series_de_archivos_distintos_se_fusionan():
    # dos Excels que cubren rangos de meses distintos: la serie resuelta
    # tiene que traer los meses de los dos, no solo los del que ganó el
    # valor vigente.
    fuentes = [
        {"consultas_nuevas_mes": VariableValue(
            95, "migracion_excel", 0.9, archivo_origen="ene_abr.xlsx",
            serie={"Enero 2026": 95.0, "Febrero 2026": 88.0}, periodo="Febrero 2026",
        )},
        {"consultas_nuevas_mes": VariableValue(
            102, "migracion_excel", 0.9, archivo_origen="may_jun.xlsx",
            serie={"Mayo 2026": 98.0, "Junio 2026": 102.0}, periodo="Junio 2026",
        )},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["consultas_nuevas_mes"].serie == {
        "Enero 2026": 95.0, "Febrero 2026": 88.0, "Mayo 2026": 98.0, "Junio 2026": 102.0,
    }


def test_periodo_en_comun_con_valores_distintos_gana_mayor_confianza_en_la_serie():
    fuentes = [
        {"consultas_nuevas_mes": VariableValue(
            88, "migracion_excel", 0.5, archivo_origen="a.xlsx",
            serie={"Febrero 2026": 88.0}, periodo="Febrero 2026",
        )},
        {"consultas_nuevas_mes": VariableValue(
            90, "migracion_excel", 0.9, archivo_origen="b.xlsx",
            serie={"Febrero 2026": 90.0}, periodo="Febrero 2026",
        )},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["consultas_nuevas_mes"].serie == {"Febrero 2026": 90.0}


def test_periodo_empatado_con_valores_distintos_genera_conflicto():
    fuentes = [
        {"consultas_nuevas_mes": VariableValue(
            88, "migracion_excel", 0.8, archivo_origen="a.xlsx",
            serie={"Febrero 2026": 88.0}, periodo="Febrero 2026",
        )},
        {"consultas_nuevas_mes": VariableValue(
            95, "migracion_excel", 0.75, archivo_origen="b.xlsx",
            serie={"Febrero 2026": 95.0}, periodo="Febrero 2026",
        )},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert "consultas_nuevas_mes" not in resueltas
    assert len(conflictos) == 1
    assert conflictos[0].variable == "consultas_nuevas_mes"


# ---------------------------------------------------------------------------
# Fase E: caso mixto — una fuente trae serie (fecha), otra no. Bug real
# encontrado por Felipe probando contra la API: presupuestos_emitidos del
# Excel (vigente=54, junio, con serie Ene-Jun) vs. el mismo dato del CSV
# (56, sin columna_periodo declarada para esa hoja, sin serie). Antes de
# este fix, `all(c.serie...)` daba False y todo caía al camino de comparar
# `.valor` a secas — comparando el vigente de un mes contra el total de
# otro como si fueran la misma pregunta.
# ---------------------------------------------------------------------------

def _serie_excel_ene_jun(vigente_junio: float) -> dict:
    return {"2026-01": 95.0, "2026-02": 88.0, "2026-03": 56.0, "2026-04": 52.0,
            "2026-05": 50.0, "2026-06": vigente_junio}


def test_mixto_con_coincidencia_resuelve_con_la_fuente_con_fecha_sin_conflicto():
    """Si el escalar sin fecha coincide con el vigente de la fuente con
    fecha, no hay nada que preguntar — no es una discrepancia, es una
    confirmación."""
    fuentes = [
        {"presupuestos_emitidos": VariableValue(
            56, "migracion_excel:Resumen mensual", 0.9,
            serie=_serie_excel_ene_jun(56.0), periodo="2026-06",
        )},
        {"presupuestos_emitidos": VariableValue(56, "migracion_excel", 0.9)},  # sin serie, coincide
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["presupuestos_emitidos"].valor == 56


def test_mixto_con_discrepancia_es_el_caso_real_54_vs_56():
    """El fixture exacto que reportó Felipe: Excel vigente=54 (junio, con
    serie), CSV=56 (sin fecha). Sigue bloqueando — Felipe pidió explícitamente
    no auto-resolver — pero con tipo="cobertura_distinta", no
    "valores_distintos": no es necesariamente un error, puede ser un mes
    distinto."""
    fuentes = [
        {"presupuestos_emitidos": VariableValue(
            54, "migracion_excel:Resumen mensual", 0.9,
            serie=_serie_excel_ene_jun(54.0), periodo="2026-06",
        )},
        {"presupuestos_emitidos": VariableValue(56, "migracion_excel", 0.9)},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert "presupuestos_emitidos" not in resueltas, "sigue bloqueando, no auto-resuelve"
    assert len(conflictos) == 1
    c = conflictos[0]
    assert c.tipo == "cobertura_distinta"
    valores = {cand["valor"] for cand in c.candidatos}
    assert valores == {54, 56}


def test_mixto_donde_las_fuentes_con_fecha_ya_disienten_gana_el_conflicto_interno():
    """Dos fuentes CON fecha que ya disienten entre sí para el mismo
    período es un conflicto real (tipo por defecto, "valores_distintos") —
    la fuente sin fecha no cambia esa naturaleza, sólo se anexa como
    contexto adicional en los candidatos."""
    fuentes = [
        {"consultas_nuevas_mes": VariableValue(
            88, "migracion_excel", 0.8, archivo_origen="a.xlsx",
            serie={"2026-02": 88.0}, periodo="2026-02",
        )},
        {"consultas_nuevas_mes": VariableValue(
            95, "migracion_excel", 0.75, archivo_origen="b.xlsx",
            serie={"2026-02": 95.0}, periodo="2026-02",
        )},
        {"consultas_nuevas_mes": VariableValue(200, "migracion_excel", 0.9)},  # sin serie
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert "consultas_nuevas_mes" not in resueltas
    assert len(conflictos) == 1
    c = conflictos[0]
    assert c.tipo == "valores_distintos", "el conflicto real es entre las fuentes con fecha, no cobertura distinta"
    valores = {cand["valor"] for cand in c.candidatos}
    assert valores == {88, 95, 200}, "la fuente sin fecha queda anexada como contexto"


def test_mixto_sin_fecha_en_ninguna_serie_util_cae_al_camino_escalar():
    """Si la única fuente con serie tiene una serie vacía/sin período
    útil (caso borde), el fallback compara escalares como si nadie
    tuviera fecha — mismo camino de siempre, sin romper."""
    fuentes = [
        {"no_shows": VariableValue(13, "migracion_excel", 0.9, serie={})},  # serie vacía => falsy
        {"no_shows": VariableValue(13, "migracion_foto", 0.5)},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["no_shows"].valor == 13


# ---------------------------------------------------------------------------
# Fase D2: monto_presupuestos_emitidos — variable nueva (schema.py,
# vocabulario, no entra a ningún KPIFormula) para que el "Presupuestado
# total" del Excel y la suma real del CSV tengan dónde chocar. No cambia
# nada acá: es el mismo mecanismo mixto de la Fase E, con el fixture real
# de Felipe (14.560.000 vs 17.849.000, 22,6% de diferencia).
# ---------------------------------------------------------------------------

def test_monto_presupuestos_emitidos_choca_con_el_fixture_real_de_felipe():
    """Sin esta variable, el "Presupuestado total" del Excel (14.560.000)
    y la suma real del CSV (17.849.000) no tenían con qué compararse —
    resolver_conflictos ni siquiera las veía como la misma variable. Con
    monto_presupuestos_emitidos declarada, el conflicto salta solo, sin
    ningún cambio en conflictos.py: el Excel trae serie (columna_periodo),
    el CSV no, así que es el camino mixto de la Fase E, tipo="cobertura_distinta"."""
    serie_excel = {
        "2026-01": 2_450_000.0, "2026-02": 2_310_000.0, "2026-03": 2_180_000.0,
        "2026-04": 2_390_000.0, "2026-05": 2_670_000.0, "2026-06": 14_560_000.0,
    }
    fuentes = [
        {"monto_presupuestos_emitidos": VariableValue(
            14_560_000.0, "migracion_excel:Resumen mensual", 0.9,
            serie=serie_excel, periodo="2026-06",
        )},
        {"monto_presupuestos_emitidos": VariableValue(17_849_000.0, "migracion_excel", 0.9)},  # CSV sin serie
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert "monto_presupuestos_emitidos" not in resueltas, "sigue bloqueando, no auto-resuelve"
    assert len(conflictos) == 1
    c = conflictos[0]
    assert c.variable == "monto_presupuestos_emitidos"
    assert c.tipo == "cobertura_distinta"
    valores = {cand["valor"] for cand in c.candidatos}
    assert valores == {14_560_000.0, 17_849_000.0}
    diferencia_pct = round(100 * (17_849_000.0 - 14_560_000.0) / 14_560_000.0, 1)
    assert diferencia_pct == 22.6, "el 22,6% que reportó Felipe, confirmado con la variable nueva"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
