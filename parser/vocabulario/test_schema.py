"""
test_schema.py

Sin pytest: corre con `python -m parser.vocabulario.test_schema`.
Cubre el hallazgo #4 (E2E): dos variables de vocabulario nuevas —
`turnos_cancelados` y `pacientes_activos_cartera` — deben quedar declaradas
en `VARIABLE_TYPES`/`METRICAS` con `no_confundir_con` para que un extractor
no las funda con `no_shows` / `pacientes_atendidos_periodo`, y deben quedar
EXCLUIDAS de `ETAPAS_EMBUDO`/`DENOMINADORES_VOLUMEN` (una no es etapa de
embudo, la otra es un stock, no un volumen de trabajo del período).

También cubre Slice 2 (poda de KPIs): `KPI_FORMULAS` quedó en 16 entradas
tras remover los IDs 11/14/17/18/20 (sin renumerar los que quedan), y
`ltv_real()` sigue siendo el único camino de cálculo de LTV.
"""

from parser.vocabulario.schema import (
    DENOMINADORES_VOLUMEN,
    ETAPAS_EMBUDO,
    KPI_BY_ID,
    KPI_FORMULAS,
    METRICAS,
    VARIABLE_TYPES,
)


def test_turnos_cancelados_declarada_como_conteo_entero():
    assert VARIABLE_TYPES.get("turnos_cancelados") == "int", (
        f"turnos_cancelados debe ser 'int', llegó {VARIABLE_TYPES.get('turnos_cancelados')!r}"
    )
    info = METRICAS.get("turnos_cancelados")
    assert info is not None, "turnos_cancelados debe tener entrada en METRICAS"
    assert "no_shows" in info.no_confundir_con, (
        f"turnos_cancelados.no_confundir_con debe mencionar no_shows: {info.no_confundir_con!r}"
    )


def test_pacientes_activos_cartera_declarada_como_conteo_entero():
    assert VARIABLE_TYPES.get("pacientes_activos_cartera") == "int", (
        f"pacientes_activos_cartera debe ser 'int', llegó {VARIABLE_TYPES.get('pacientes_activos_cartera')!r}"
    )
    info = METRICAS.get("pacientes_activos_cartera")
    assert info is not None, "pacientes_activos_cartera debe tener entrada en METRICAS"
    assert "pacientes_atendidos_periodo" in info.no_confundir_con, (
        f"pacientes_activos_cartera.no_confundir_con debe mencionar pacientes_atendidos_periodo: "
        f"{info.no_confundir_con!r}"
    )


def test_turnos_cancelados_no_es_etapa_de_embudo_ni_denominador():
    # No es una etapa secuencial del embudo (agendado -> asistido -> ...) ni
    # un volumen de trabajo válido como denominador — es la contracara de
    # no_shows, que tampoco está en ninguna de las dos listas.
    assert "turnos_cancelados" not in ETAPAS_EMBUDO
    assert "turnos_cancelados" not in DENOMINADORES_VOLUMEN


def test_pacientes_activos_cartera_no_es_etapa_de_embudo_ni_denominador():
    # Es un STOCK (foto de la cartera activa hoy), igual que
    # pacientes_inactivos_total — ninguno de los dos representa volumen de
    # trabajo del período, así que ninguno entra a estas whitelists.
    assert "pacientes_inactivos_total" not in DENOMINADORES_VOLUMEN, (
        "regresión del fixture de comparación: pacientes_inactivos_total no debería estar acá"
    )
    assert "pacientes_activos_cartera" not in ETAPAS_EMBUDO
    assert "pacientes_activos_cartera" not in DENOMINADORES_VOLUMEN


def test_nuevas_variables_tienen_pregunta_de_wizard():
    # preguntas_wizard.PREGUNTAS_WIZARD es un dict a mano, NO derivado de
    # schema.py (checklist del skill parser-nueva-variable) — sin esta
    # entrada, el wizard nunca pregunta el dato aunque la variable ya exista
    # en el vocabulario, y la KPI que la necesita queda bloqueada para
    # siempre en el flujo manual.
    from parser.cobertura_calidad.preguntas_wizard import PREGUNTAS_WIZARD, obtener_pregunta

    for var in ("turnos_cancelados", "pacientes_activos_cartera"):
        assert var in PREGUNTAS_WIZARD, f"{var} debe tener una pregunta de wizard"
        pregunta = obtener_pregunta(var)
        assert pregunta is not None and pregunta.variable == var
        assert pregunta.pregunta, f"{var} no puede tener texto de pregunta vacío"


def test_kpi_formulas_tiene_16_entradas_tras_la_poda_de_slice_2():
    assert len(KPI_FORMULAS) == 16, (
        f"KPI_FORMULAS debería tener 16 entradas post-poda, tiene {len(KPI_FORMULAS)}"
    )
    assert len(KPI_BY_ID) == 16


def test_kpis_podados_no_resuelven_en_kpi_by_id():
    # 11 (Throughput), 14 (slot de fórmula LTV), 17 (horas-persona
    # liberadas), 18 (tareas sin backup), 20 (rentabilidad por tratamiento)
    # — podados por no tener linkeo a catálogo, benchmark real ni uso en
    # frontend. IDs NO renumerados: 21 (penetración de reactivación) sigue
    # siendo 21 para no romper kpi_objetivo/kpis_secundarios del catálogo.
    for kpi_id in (11, 14, 17, 18, 20):
        assert kpi_id not in KPI_BY_ID, f"KPI {kpi_id} debería haberse podado en Slice 2"
    assert 21 in KPI_BY_ID, "KPI 21 no se renumera aunque el set haya bajado a 16 entradas"


def test_ltv_real_sigue_siendo_el_unico_camino_de_ltv():
    # KPI 14 (que promediaba ingreso_por_paciente) se podó — ltv_real()
    # en metricas_paciente.py, independiente de KPI_FORMULAS, debe seguir
    # funcionando sin que la poda la afecte.
    from parser.pacientes.metricas_paciente import ltv_real

    ledger = {
        "P1": [{"periodo": "2026-01", "tipo_evento": "pago", "monto": 50000, "tratamiento": "Control"}],
    }
    assert ltv_real(ledger) == {"P1": 50000.0}


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
