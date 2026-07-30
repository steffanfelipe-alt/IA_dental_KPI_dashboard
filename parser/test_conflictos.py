"""
test_conflictos.py

Sin pytest (no está instalado en el entorno): corre con `python3 test_conflictos.py`.
Casos del plan "resolución de conflictos de variables migradas".
"""

from coverage import VariableValue
from conflictos import fusionar_candidatos, resolver_conflictos, UMBRAL_EMPATE


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
    """Fase H1: el valor confirmado sigue ganando SIEMPRE — eso no cambió.
    Lo que cambió es que un candidato que lo contradice ya no se ignora en
    silencio: antes `conflictos` daba vacío acá; ahora avisa con
    tipo="contradice_confirmado" sin dejar de resolver con el confirmado."""
    fuentes = [
        {"no_shows": VariableValue(56, "confirmado_por_dueno", 1.0)},
        {"no_shows": VariableValue(99, "migracion_excel", 1.0, archivo_origen="turnos_nuevo.xlsx")},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert resueltas["no_shows"].valor == 56
    assert resueltas["no_shows"].fuente == "confirmado_por_dueno"
    assert len(conflictos) == 1
    assert conflictos[0].tipo == "contradice_confirmado"
    valores = {c["valor"] for c in conflictos[0].candidatos}
    assert valores == {56, 99}


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


# ---------------------------------------------------------------------------
# Fase G1: _resolver_por_periodo reconstruía el VariableValue ganador
# pasando sólo 5 de 9 campos — se perdían archivo_origen, trazabilidad,
# etiquetas_originales y periodos_no_reconocidos incluso SIN conflicto,
# con un solo candidato. Acá se prueba que ahora se preservan.
# ---------------------------------------------------------------------------

from trazabilidad import Trazabilidad


def test_un_solo_candidato_con_serie_conserva_archivo_y_trazabilidad():
    """El caso más simple posible: una sola fuente, con serie, sin
    conflicto — antes de G1 esto ya perdía archivo_origen y trazabilidad,
    aunque no había nada que resolver."""
    traza = Trazabilidad(origen="celda", hoja="Resumen mensual")
    fuentes = [{
        "consultas_nuevas_mes": VariableValue(
            105, "migracion_excel:Resumen mensual", 0.9, archivo_origen="clinica.xlsx",
            serie={"2026-05": 98.0, "2026-06": 105.0}, periodo="2026-06",
            trazabilidad=traza,
        ),
    }]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    r = resueltas["consultas_nuevas_mes"]
    assert r.archivo_origen == "clinica.xlsx", "antes de G1 esto daba None"
    assert r.trazabilidad is traza, "antes de G1 esto daba None"


def test_periodos_no_reconocidos_se_fusionan_de_ambos_candidatos():
    """Dos archivos con series que no chocan (mismo valor en el período
    común), cada uno con SUS PROPIOS períodos_no_reconocidos — la unión
    debe traer los de los dos, no sólo los del último ganador."""
    fuentes = [
        {"monto_cobrado": VariableValue(
            100.0, "migracion_excel:A", 0.9, archivo_origen="a.xlsx",
            serie={"2026-01": 100.0}, periodo="2026-01",
            periodos_no_reconocidos={"Totales": 999.0},
        )},
        {"monto_cobrado": VariableValue(
            100.0, "migracion_excel:B", 0.85, archivo_origen="b.xlsx",
            serie={"2026-01": 100.0}, periodo="2026-01",
            periodos_no_reconocidos={"Promedio": 50.0},
        )},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    r = resueltas["monto_cobrado"]
    assert r.periodos_no_reconocidos == {"Totales": 999.0, "Promedio": 50.0}


def test_etiquetas_originales_vienen_del_ganador_de_cada_periodo():
    """Dos fuentes con distinta cobertura de meses (sin conflicto real,
    cada una aporta períodos distintos): la etiqueta cruda de cada período
    debe venir del candidato que efectivamente ganó ESE período, fusionada
    en vez de tomada de un solo candidato."""
    fuentes = [
        {"turnos_agendados": VariableValue(
            76, "migracion_excel:A", 0.9, archivo_origen="a.xlsx",
            serie={"2026-01": 70.0, "2026-02": 76.0}, periodo="2026-02",
            etiquetas_originales={"2026-01": "Ene-26", "2026-02": "Feb-26"},
        )},
        {"turnos_agendados": VariableValue(
            80, "migracion_excel:B", 0.5, archivo_origen="b.xlsx",
            serie={"2026-03": 80.0}, periodo="2026-03",
            etiquetas_originales={"2026-03": "March 2026"},
        )},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    r = resueltas["turnos_agendados"]
    assert r.etiquetas_originales == {
        "2026-01": "Ene-26", "2026-02": "Feb-26", "2026-03": "March 2026",
    }


# ---------------------------------------------------------------------------
# Fase H1: un archivo nuevo que contradice un valor ya confirmado por el
# dueño ya no se ignora en silencio — abre un Conflicto nuevo
# (tipo="contradice_confirmado"), aunque sigue resolviendo con el
# confirmado (Felipe: "sigue ganando tu valor hasta que respondas").
# ---------------------------------------------------------------------------

def test_confirmado_sin_contradiccion_no_genera_conflicto():
    """Contraste positivo: si el archivo nuevo COINCIDE con lo ya
    confirmado, no hay nada que avisar."""
    fuentes = [
        {"no_shows": VariableValue(56, "confirmado_por_dueno", 1.0)},
        {"no_shows": VariableValue(56, "migracion_excel", 0.9, archivo_origen="turnos_nuevo.xlsx")},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["no_shows"].valor == 56


def test_confirmado_con_dos_candidatos_discrepantes_los_incluye_a_ambos():
    fuentes = [
        {"no_shows": VariableValue(56, "confirmado_por_dueno", 1.0)},
        {"no_shows": VariableValue(60, "migracion_excel", 0.8, archivo_origen="a.xlsx")},
        {"no_shows": VariableValue(70, "migracion_excel", 0.7, archivo_origen="b.xlsx")},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert resueltas["no_shows"].valor == 56
    assert len(conflictos) == 1
    valores = {c["valor"] for c in conflictos[0].candidatos}
    assert valores == {56, 60, 70}


# ---------------------------------------------------------------------------
# Fase I7: _candidato() ahora trae la cuenta completa, no sólo 4 claves
# ---------------------------------------------------------------------------

def test_candidato_escalar_trae_explicacion():
    fuentes = [
        {"no_shows": VariableValue(56, "migracion_excel", 0.8, archivo_origen="a.xlsx")},
        {"no_shows": VariableValue(60, "migracion_excel", 0.75, archivo_origen="b.xlsx")},  # diff < UMBRAL_EMPATE
    ]
    _, conflictos = resolver_conflictos(fuentes)
    assert len(conflictos) == 1
    for c in conflictos[0].candidatos:
        assert "explicacion" in c
        assert c["explicacion"]  # nunca vacío — explicar() siempre devuelve algo, aunque sea degradado
        assert "serie" not in c  # sin serie, no hay nada que agregar


def test_candidato_con_serie_trae_serie_completa_y_periodo_vigente():
    serie_a = {"2026-01": 100, "2026-02": 200}
    serie_b = {"2026-01": 999, "2026-02": 200}  # discrepan en enero
    fuentes = [
        {"no_shows": VariableValue(200, "migracion_excel:A", 0.8, serie=serie_a, periodo="2026-02")},
        {"no_shows": VariableValue(200, "migracion_excel:B", 0.8, serie=serie_b, periodo="2026-02")},
    ]
    _, conflictos = resolver_conflictos(fuentes)
    assert len(conflictos) == 1
    for c in conflictos[0].candidatos:
        assert "serie" in c
        assert isinstance(c["serie"], dict)
        assert "periodo_vigente" in c


def test_vigente_es_cronologico_no_por_orden_de_aparicion():
    """Fase I8: bug real encontrado leyendo el código. Si el candidato con
    jul-dic se procesa ANTES que el de ene-jun, el vigente resultante
    tiene que seguir siendo diciembre (el mes más reciente), no junio
    (el último en orden de inserción)."""
    fuentes = [
        {"no_shows": VariableValue(12, "migracion_excel:B", 0.9, serie={
            "2026-07": 7, "2026-08": 8, "2026-09": 9, "2026-10": 10, "2026-11": 11, "2026-12": 12,
        }, periodo="2026-12")},
        {"no_shows": VariableValue(6, "migracion_excel:A", 0.9, serie={
            "2026-01": 1, "2026-02": 2, "2026-03": 3, "2026-04": 4, "2026-05": 5, "2026-06": 6,
        }, periodo="2026-06")},
    ]
    resueltas, conflictos = resolver_conflictos(fuentes)
    assert conflictos == []
    assert resueltas["no_shows"].valor == 12  # diciembre, no junio
    assert resueltas["no_shows"].periodo == "2026-12"


def test_candidato_con_trazabilidad_usa_explicar_de_verdad():
    from trazabilidad import Trazabilidad
    traza = Trazabilidad(hoja="Resumen mensual", columna="Presupuestos", n_registros=6)
    fuentes = [
        {"no_shows": VariableValue(56, "migracion_excel", 0.8, archivo_origen="a.xlsx", trazabilidad=traza)},
        {"no_shows": VariableValue(60, "migracion_excel", 0.75, archivo_origen="b.xlsx")},  # diff < UMBRAL_EMPATE
    ]
    _, conflictos = resolver_conflictos(fuentes)
    explicaciones = [c["explicacion"] for c in conflictos[0].candidatos]
    assert any("Resumen mensual" in e for e in explicaciones)
    assert any("sin traza registrada" in e for e in explicaciones)  # el candidato b, sin trazabilidad


# ---------------------------------------------------------------------------
# Fase I8: fusionar_candidatos — "elegir los dos" en vez de forzar uno
# ---------------------------------------------------------------------------

def test_fusionar_un_solo_candidato_preserva_su_serie():
    """El bug que arregla I8: antes, "elegir un candidato" en
    resolver_conflicto siempre producía un escalar pelado, aunque el
    candidato tuviera 6 meses de historia. Acá se prueba la pieza que lo
    resuelve: con un solo candidato, su serie sobrevive intacta."""
    candidatos = [{"valor": 5940072.0, "serie": {"2026-01": 4459815.0, "2026-03": 5940072.0}, "periodo_vigente": "2026-03"}]
    fusion = fusionar_candidatos(candidatos)
    assert fusion["serie"] == {"2026-01": 4459815.0, "2026-03": 5940072.0}
    assert fusion["periodo"] == "2026-03"
    assert fusion["valor"] == 5940072.0


def test_fusionar_dos_candidatos_con_serie_los_combina_por_periodo():
    candidatos = [
        {"valor": 12, "serie": {"2026-07": 7, "2026-12": 12}},
        {"valor": 6, "serie": {"2026-01": 1, "2026-06": 6}},
    ]
    fusion = fusionar_candidatos(candidatos)
    assert fusion["serie"] == {"2026-07": 7, "2026-12": 12, "2026-01": 1, "2026-06": 6}
    assert fusion["periodo"] == "2026-12"  # cronológico, no por orden de aparición
    assert fusion["valor"] == 12


def test_fusionar_serie_mas_escalar_con_periodo_asignado():
    """El caso real que motivó I8: un candidato con serie (Excel, ene-jun)
    y otro escalar sin fecha (CSV, total de marzo) — con el dueño diciendo
    "eso es marzo", se fusiona en la serie en vez de perderse."""
    candidatos = [
        {"valor": 54.0, "serie": {"2026-01": 40.0, "2026-03": 50.0, "2026-06": 54.0}},
        {"valor": 56},  # sin serie — el CSV sin columna_periodo
    ]
    fusion = fusionar_candidatos(candidatos, periodos_de_escalares={1: "2026-03"})
    assert fusion["serie"]["2026-03"] == 56  # el escalar pisa el valor de marzo del Excel
    assert fusion["periodo"] == "2026-06"  # el vigente sigue siendo el mes más reciente
    assert fusion["valor"] == 54.0


def test_fusionar_escalar_sin_periodo_asignado_no_aporta_a_la_serie():
    candidatos = [
        {"valor": 54.0, "serie": {"2026-06": 54.0}},
        {"valor": 56},  # sin serie y sin período asignado
    ]
    fusion = fusionar_candidatos(candidatos)  # sin periodos_de_escalares
    assert fusion["serie"] == {"2026-06": 54.0}  # el 56 no se coló en ningún lado


def test_fusionar_sin_series_ni_periodos_cae_al_ultimo_candidato():
    candidatos = [{"valor": 54.0}, {"valor": 56}]
    fusion = fusionar_candidatos(candidatos)
    assert fusion["valor"] == 56
    assert fusion["serie"] is None


# ---------------------------------------------------------------------------
# Fase I8: resolver_conflicto con `candidatos=` (vía pipeline.py)
# ---------------------------------------------------------------------------

def test_resolver_conflicto_con_un_candidato_preserva_la_serie():
    import pipeline
    resultado = pipeline.resolver_conflicto(
        "monto_cobrado", {},
        candidatos=[{"valor": 5940072.0, "serie": {"2026-01": 4459815.0, "2026-03": 5940072.0}}],
    )
    vv = resultado["variables"]["monto_cobrado"]
    assert vv.serie == {"2026-01": 4459815.0, "2026-03": 5940072.0}
    assert vv.fuente == "confirmado_por_dueno"


def test_resolver_conflicto_con_dos_candidatos_fusiona():
    import pipeline
    resultado = pipeline.resolver_conflicto(
        "presupuestos_emitidos", {},
        candidatos=[
            {"valor": 54.0, "serie": {"2026-01": 40.0, "2026-06": 54.0}},
            {"valor": 56},
        ],
        periodos_de_escalares={1: "2026-03"},
    )
    vv = resultado["variables"]["presupuestos_emitidos"]
    assert vv.serie["2026-03"] == 56
    assert vv.valor == 54.0  # vigente sigue siendo junio


def test_resolver_conflicto_sin_candidatos_sigue_igual_que_siempre():
    """Retrocompatibilidad: un llamador viejo que pasa valor= sigue dando
    exactamente el mismo escalar pelado de siempre."""
    import pipeline
    resultado = pipeline.resolver_conflicto("no_shows", {}, valor=56)
    vv = resultado["variables"]["no_shows"]
    assert vv.valor == 56
    assert vv.serie is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
