"""
test_cruces.py

Sin pytest, sin API (cruces.py no importa anthropic): corre con
`python -m parser.catalogo.test_cruces`. Fase B del plan de evolución — cruces
determinísticos fuera de las 21 KPIFormula fijas.
"""

from parser.cobertura_calidad.coverage import VariableValue
from parser.catalogo.cruces import (
    Cruce,
    MINIMO_PERIODOS_COMUNES,
    _aplicar,
    _series_comunes,
    calcular_cruce,
    generar_cruces,
    generar_cruces_algebraicos,
    generar_cruces_embudo,
)
from parser.vocabulario.schema import ETAPAS_EMBUDO


def _vv(valor, serie=None, confianza=0.9):
    return VariableValue(valor, "migracion_excel", confianza, serie=serie)


SERIE_A = {"2026-01": 100.0, "2026-02": 110.0, "2026-03": 120.0}
SERIE_B = {"2026-01": 10.0, "2026-02": 11.0, "2026-03": 12.0}


# ---------------------------------------------------------------------------
# _aplicar: aritmética base
# ---------------------------------------------------------------------------

def test_aplicar_division_porcentaje_usa_escala_0_100():
    assert _aplicar("/", 30, 60, "%") == 50.0


def test_aplicar_division_monto_no_multiplica_por_100():
    assert _aplicar("/", 100, 4, "monto_ars/unidad") == 25.0


def test_aplicar_resta():
    assert _aplicar("-", 100, 40, "monto_ars") == 60.0


def test_aplicar_division_por_cero_da_none_no_excepcion():
    assert _aplicar("/", 100, 0, "%") is None


def test_aplicar_operacion_desconocida_explota_en_vez_de_fallar_silencioso():
    try:
        _aplicar("*", 1, 1, "%")
    except ValueError:
        pass
    else:
        raise AssertionError("una operación no declarada debe fallar ruidosamente")


# ---------------------------------------------------------------------------
# calcular_cruce: guardarraíles
# ---------------------------------------------------------------------------

def test_calcular_cruce_basico():
    c = calcular_cruce(
        "Cruce de prueba", "var_a", "/", "var_b", "%",
        _vv(120, SERIE_A), _vv(12, SERIE_B), "algebra", "justificación",
    )
    assert isinstance(c, Cruce)
    assert c.periodos_comunes == 3
    assert c.valor == round(120 / 12 * 100, 1)
    assert c.serie["2026-01"] == round(100 / 10 * 100, 1)


def test_calcular_cruce_sin_serie_da_none():
    assert calcular_cruce("x", "a", "/", "b", "%", _vv(10), _vv(5), "algebra", "j") is None


def test_calcular_cruce_sin_periodos_comunes_da_none():
    serie_a = {"2026-01": 100.0}
    serie_b = {"2026-05": 10.0}
    assert calcular_cruce("x", "a", "/", "b", "%", _vv(100, serie_a), _vv(10, serie_b), "algebra", "j") is None


def test_calcular_cruce_un_solo_periodo_comun_no_alcanza():
    """MINIMO_PERIODOS_COMUNES = 2: un solo punto no es tendencia."""
    serie_a = {"2026-01": 100.0, "2026-02": 200.0}
    serie_b = {"2026-01": 10.0}
    assert MINIMO_PERIODOS_COMUNES == 2
    assert calcular_cruce("x", "a", "/", "b", "%", _vv(100, serie_a), _vv(10, serie_b), "algebra", "j") is None


def test_calcular_cruce_denominador_cero_en_un_periodo_lo_salta_no_lo_inventa():
    serie_a = {"2026-01": 100.0, "2026-02": 200.0, "2026-03": 300.0}
    serie_b = {"2026-01": 10.0, "2026-02": 0.0, "2026-03": 30.0}
    c = calcular_cruce("x", "a", "/", "b", "%", _vv(100, serie_a), _vv(30, serie_b), "algebra", "j")
    assert c is not None
    assert "2026-02" not in c.serie, "el período con denominador 0 no puede inventar un valor"
    assert set(c.serie) == {"2026-01", "2026-03"}


def test_calcular_cruce_denominador_cero_en_todos_da_none():
    serie_a = {"2026-01": 100.0, "2026-02": 200.0}
    serie_b = {"2026-01": 0.0, "2026-02": 0.0}
    assert calcular_cruce("x", "a", "/", "b", "%", _vv(100, serie_a), _vv(0, serie_b), "algebra", "j") is None


def test_calcular_cruce_propaga_la_confianza_minima():
    c = calcular_cruce(
        "x", "a", "/", "b", "%",
        _vv(120, SERIE_A, confianza=0.9), _vv(12, SERIE_B, confianza=0.5),
        "algebra", "j",
    )
    assert c.confianza == 0.5


def test_series_comunes_respeta_orden_de_aparicion_de_la_primera_serie():
    """Misma convención que coverage._calcular_serie_kpi: el orden temporal
    lo da la serie de A, no un sort alfabético de las claves."""
    serie_a = {"2026-03": 3.0, "2026-01": 1.0, "2026-02": 2.0}
    serie_b = {"2026-01": 10.0, "2026-02": 20.0, "2026-03": 30.0}
    pares = _series_comunes(_vv(0, serie_a), _vv(0, serie_b))
    assert list(pares.keys()) == ["2026-03", "2026-01", "2026-02"]


# ---------------------------------------------------------------------------
# Capa 1 — embudo declarado
# ---------------------------------------------------------------------------

def _variables_embudo_completo():
    """Todas las etapas del embudo, con la misma serie de 3 puntos
    (valores crecientes) para poder generar la matriz completa."""
    variables = {}
    for i, etapa in enumerate(ETAPAS_EMBUDO):
        base = 100 - i * 5  # decreciente etapa a etapa, como un embudo real
        variables[etapa] = _vv(base, {
            "2026-01": float(base), "2026-02": float(base + 1), "2026-03": float(base + 2),
        })
    return variables


def test_embudo_genera_todos_los_pares_posteriores_sobre_anteriores():
    from itertools import combinations
    variables = _variables_embudo_completo()
    cruces = generar_cruces_embudo(variables)
    esperados = set(combinations(ETAPAS_EMBUDO, 2))  # (anterior, posterior) por orden de ETAPAS_EMBUDO
    obtenidos = {(c.variable_b, c.variable_a) for c in cruces}  # var_b=anterior, var_a=posterior
    assert obtenidos == esperados, "deben generarse los C(n,2) pares, ninguno de más ni de menos"


def test_embudo_nunca_invierte_la_direccion_anterior_sobre_posterior():
    """La razón siempre es posterior/anterior — nunca al revés (eso daría
    una 'tasa de conversión' mayor a 100% sin sentido en el embudo)."""
    variables = _variables_embudo_completo()
    idx = {etapa: i for i, etapa in enumerate(ETAPAS_EMBUDO)}
    for c in generar_cruces_embudo(variables):
        assert idx[c.variable_a] > idx[c.variable_b], f"{c.variable_a} debería ser posterior a {c.variable_b}"


def test_embudo_variable_faltante_simplemente_no_genera_esos_pares():
    variables = _variables_embudo_completo()
    del variables[ETAPAS_EMBUDO[0]]  # sacar la primera etapa
    cruces = generar_cruces_embudo(variables)
    for c in cruces:
        assert ETAPAS_EMBUDO[0] not in (c.variable_a, c.variable_b)


# ---------------------------------------------------------------------------
# Capa 2 — álgebra de unidades: rechazo dimensional
# ---------------------------------------------------------------------------

def test_algebra_conteo_dividido_conteo_generico_queda_fuera_de_capa_2():
    """conteo÷conteo es EXCLUSIVO del embudo (capa 1) — capa 2 nunca lo
    produce, ni siquiera para dos conteos que no estén en ETAPAS_EMBUDO."""
    variables = {
        "resenas_nuevas": _vv(5, {"2026-01": 5.0, "2026-02": 6.0}),
        "no_shows": _vv(3, {"2026-01": 3.0, "2026-02": 4.0}),
    }
    cruces = generar_cruces_algebraicos(variables)
    assert cruces == [], "resenas_nuevas y no_shows no están en ETAPAS_EMBUDO: ningún cruce conteo/conteo debe salir de acá"


def test_algebra_horas_dividido_monto_no_esta_declarado_no_se_genera():
    """horas÷monto no está en OPERACIONES_LEGALES (sólo monto÷horas) — si
    esta combinación llegara a generarse sería dimensionalmente al revés."""
    variables = {
        "horas_sillon_ocupadas": _vv(100, {"2026-01": 100.0, "2026-02": 110.0}),
        "monto_cobrado": _vv(500000, {"2026-01": 500000.0, "2026-02": 550000.0}),
    }
    cruces = generar_cruces_algebraicos(variables)
    invertidos = [c for c in cruces if c.variable_a == "horas_sillon_ocupadas" and c.variable_b == "monto_cobrado"]
    assert invertidos == [], "horas ÷ monto no está declarado; sólo monto ÷ horas lo está"


def test_algebra_genera_monto_dividido_conteo():
    variables = {
        "monto_cobrado": _vv(600000, {"2026-01": 600000.0, "2026-02": 650000.0}),
        "pacientes_atendidos_periodo": _vv(60, {"2026-01": 60.0, "2026-02": 65.0}),
    }
    cruces = generar_cruces_algebraicos(variables)
    assert any(
        c.variable_a == "monto_cobrado" and c.variable_b == "pacientes_atendidos_periodo" and c.unidad == "monto_ars/unidad"
        for c in cruces
    )


def test_algebra_monto_menos_monto_no_duplica_direccion_espejada():
    """monto_a - monto_b y monto_b - monto_a no deben generarse ambas — un
    solo cruce por par (la dirección la elige la magnitud, ver Fase G4;
    lo que este test protege es que nunca sean dos)."""
    variables = {
        "monto_cobrado": _vv(600000, {"2026-01": 600000.0, "2026-02": 650000.0}),
        "gasto_captacion": _vv(50000, {"2026-01": 50000.0, "2026-02": 55000.0}),
    }
    cruces = [c for c in generar_cruces_algebraicos(variables) if c.operacion == "-"]
    assert len(cruces) == 1, "un solo cruce de resta por par de montos, no dos direcciones"


# ---------------------------------------------------------------------------
# Fase G4: whitelist de denominadores + resta por magnitud
# ---------------------------------------------------------------------------

def test_no_shows_no_es_denominador_valido_de_un_monto():
    """No-shows no está en DENOMINADORES_VOLUMEN — 'Monto cobrado por
    No-shows' no es una métrica real (no_shows nunca es una base de
    volumen sobre la que dividir un ingreso)."""
    variables = {
        "monto_cobrado": _vv(600000, {"2026-01": 600000.0, "2026-02": 650000.0}),
        "no_shows": _vv(17, {"2026-01": 15.0, "2026-02": 17.0}),
    }
    cruces = generar_cruces_algebraicos(variables)
    assert cruces == [], "no_shows no es un denominador de volumen válido"


def test_etapa_del_embudo_si_es_denominador_valido_de_un_monto():
    """Contraste positivo del anterior: pacientes_atendidos_periodo SÍ
    está en DENOMINADORES_VOLUMEN, el cruce debe seguir generándose."""
    variables = {
        "monto_cobrado": _vv(600000, {"2026-01": 600000.0, "2026-02": 650000.0}),
        "pacientes_atendidos_periodo": _vv(60, {"2026-01": 60.0, "2026-02": 65.0}),
    }
    cruces = generar_cruces_algebraicos(variables)
    assert any(
        c.variable_a == "monto_cobrado" and c.variable_b == "pacientes_atendidos_periodo"
        for c in cruces
    )


def test_resta_de_montos_da_positivo_con_el_mayor_como_minuendo():
    """monto_facturado (mayor) − monto_cobrado (menor), nunca al revés,
    sin importar el orden alfabético de los nombres."""
    variables = {
        "monto_cobrado": _vv(6180000, {"2026-01": 6000000.0, "2026-02": 6180000.0}),
        "monto_facturado": _vv(6380000, {"2026-01": 6200000.0, "2026-02": 6380000.0}),
    }
    cruces = [c for c in generar_cruces_algebraicos(variables) if c.operacion == "-"]
    assert len(cruces) == 1
    c = cruces[0]
    assert c.variable_a == "monto_facturado" and c.variable_b == "monto_cobrado"
    assert c.valor > 0, "el mayor como minuendo — nunca debería dar negativo acá"


# ---------------------------------------------------------------------------
# Orquestador: deduplicación contra el catálogo de 21 KPIs
# ---------------------------------------------------------------------------

def _variables_catalogo_completo():
    """Variables que alimentan los 7 pares numerador/denominador ya
    declarados en KPI_FORMULAS (KPIs 3, 4, 5, 7, 8, 9, 13), más
    pacientes_atendidos_periodo para dar un cruce algebraico de verdad."""
    serie = {"2026-01": 1.0, "2026-02": 2.0, "2026-03": 3.0}
    nombres = [
        "consultas_nuevas_mes", "turnos_agendados", "no_shows",
        "presupuestos_emitidos", "presupuestos_aceptados",
        "tratamientos_iniciados", "tratamientos_completados",
        "pacientes_dados_alta", "pacientes_vuelven_control",
        "pacientes_inactivos_contactados", "pacientes_reactivados",
        "monto_cobrado", "monto_facturado", "pacientes_atendidos_periodo",
    ]
    return {n: _vv(1.0, dict(serie)) for n in nombres}


def test_generar_cruces_excluye_los_7_pares_ya_en_el_catalogo():
    variables = _variables_catalogo_completo()
    cruces = generar_cruces(variables, limite=None)
    pares_catalogo = {
        ("turnos_agendados", "consultas_nuevas_mes"),      # KPI 3
        ("no_shows", "turnos_agendados"),                  # KPI 4
        ("presupuestos_aceptados", "presupuestos_emitidos"),  # KPI 5
        ("tratamientos_completados", "tratamientos_iniciados"),  # KPI 7
        ("pacientes_vuelven_control", "pacientes_dados_alta"),  # KPI 8
        ("pacientes_reactivados", "pacientes_inactivos_contactados"),  # KPI 9
        ("monto_cobrado", "monto_facturado"),               # KPI 13
    }
    obtenidos = {(c.variable_a, c.variable_b) for c in cruces}
    interseccion = obtenidos & pares_catalogo
    assert interseccion == set(), f"estos pares ya los calcula el catálogo de 21 KPIs: {interseccion}"


def test_generar_cruces_si_solo_hay_un_par_del_catalogo_devuelve_lista_vacia():
    """Sólo las dos variables de un par ya cubierto por el catálogo (KPI 3:
    turnos_agendados/consultas_nuevas_mes, ambas en ETAPAS_EMBUDO) — sin
    ninguna otra variable que habilite un cruce nuevo, no debería quedar
    nada tras la deduplicación."""
    serie = {"2026-01": 1.0, "2026-02": 2.0}
    variables = {
        "turnos_agendados": _vv(1.0, dict(serie)),
        "consultas_nuevas_mes": _vv(1.0, dict(serie)),
    }
    assert generar_cruces(variables, limite=None) == []


# ---------------------------------------------------------------------------
# Orquestador: ranking y límite
# ---------------------------------------------------------------------------

def test_generar_cruces_respeta_el_limite():
    variables = _variables_embudo_completo()
    todos = generar_cruces(variables, limite=None)
    limitados = generar_cruces(variables, limite=3)
    assert len(limitados) == 3
    assert len(todos) > 3
    assert limitados == todos[:3], "el límite debe recortar la misma lista ya ordenada, no reordenar"


def test_generar_cruces_prioriza_mas_periodos_comunes():
    """Dos cruces posibles, uno con más períodos comunes que el otro: el
    de más períodos debe salir primero (ranking, no exclusión)."""
    serie_larga = {f"2026-{m:02d}": float(100 + m) for m in range(1, 7)}
    serie_corta = {"2026-01": 100.0, "2026-02": 101.0}
    variables = {
        "monto_cobrado": _vv(100.0, serie_larga),
        "pacientes_atendidos_periodo": _vv(10.0, {k: 10.0 for k in serie_larga}),
        "gasto_captacion": _vv(5.0, serie_corta),
    }
    cruces = generar_cruces(variables, limite=None)
    con_seis_periodos = [c for c in cruces if c.periodos_comunes == 6]
    con_dos_periodos = [c for c in cruces if c.periodos_comunes == 2]
    assert con_seis_periodos and con_dos_periodos
    assert cruces.index(con_seis_periodos[0]) < cruces.index(con_dos_periodos[0])


def test_generar_cruces_sin_variables_da_lista_vacia():
    assert generar_cruces({}) == []


# ---------------------------------------------------------------------------
# Fase F: etapa_embudo / impacto_decision — campos nuevos en Cruce, sólo los
# completa cruces_propuestos.py (capa 3). Acá se confirma que un Cruce de
# las capas 1/2 (este módulo) nunca los toca.
# ---------------------------------------------------------------------------

def test_cruce_deterministico_no_tiene_etapa_ni_impacto():
    cruce = calcular_cruce(
        nombre="x", var_a="monto_cobrado", operacion="/", var_b="pacientes_atendidos_periodo",
        unidad="monto_ars/unidad", vv_a=_vv(120.0, SERIE_A), vv_b=_vv(12.0, SERIE_B),
        origen="algebra", justificacion="test",
    )
    assert cruce.etapa_embudo == ""
    assert cruce.impacto_decision == ""


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
