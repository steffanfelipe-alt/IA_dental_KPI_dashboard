"""
test_schema.py

Sin pytest: corre con `python3 test_schema.py`.
Cubre el hallazgo #4 (E2E): dos variables de vocabulario nuevas —
`turnos_cancelados` y `pacientes_activos_cartera` — deben quedar declaradas
en `VARIABLE_TYPES`/`METRICAS` con `no_confundir_con` para que un extractor
no las funda con `no_shows` / `pacientes_atendidos_periodo`, y deben quedar
EXCLUIDAS de `ETAPAS_EMBUDO`/`DENOMINADORES_VOLUMEN` (una no es etapa de
embudo, la otra es un stock, no un volumen de trabajo del período).
"""

from schema import (
    DENOMINADORES_VOLUMEN,
    ETAPAS_EMBUDO,
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
    from preguntas_wizard import PREGUNTAS_WIZARD, obtener_pregunta

    for var in ("turnos_cancelados", "pacientes_activos_cartera"):
        assert var in PREGUNTAS_WIZARD, f"{var} debe tener una pregunta de wizard"
        pregunta = obtener_pregunta(var)
        assert pregunta is not None and pregunta.variable == var
        assert pregunta.pregunta, f"{var} no puede tener texto de pregunta vacío"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
