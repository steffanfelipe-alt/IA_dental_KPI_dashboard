"""
test_metricas_paciente.py

Sin pytest: corre con `python -m parser.pacientes.test_metricas_paciente`.
Cubre las 17 métricas de metricas_paciente.py sobre ledgers construidos a
mano (periodo ya normalizado) — no depende de matching.py ni de
extracción, para poder aislar la lógica de cada métrica.
"""

from parser.pacientes import metricas_paciente as mp


def _ev(periodo, tipo, monto=None, tratamiento=None):
    return {"fecha": periodo, "periodo": periodo, "tipo_evento": tipo, "monto": monto, "tratamiento": tratamiento}


# ---------------------------------------------------------------------------
# Riesgo y fuga
# ---------------------------------------------------------------------------

def test_no_show_recurrente_distingue_recurrencia_de_un_solo_fallo():
    ledger = {
        "recurrente": [
            _ev("2026-01", "turno_asistido"), _ev("2026-02", "turno_no_show"),
            _ev("2026-03", "turno_no_show"), _ev("2026-04", "turno_no_show"),
        ],
        "ocasional": [_ev(f"2026-{m:02d}", "turno_asistido") for m in range(1, 12)] + [_ev("2026-12", "turno_no_show")],
    }
    resultado = mp.no_show_recurrente(ledger, umbral_tasa=0.3, minimo_turnos=3)
    assert "recurrente" in resultado and resultado["recurrente"] == 0.75
    assert "ocasional" not in resultado


def test_no_show_recurrente_ignora_pacientes_con_pocos_datos():
    ledger = {"nuevo": [_ev("2026-01", "turno_no_show"), _ev("2026-02", "turno_no_show")]}
    assert mp.no_show_recurrente(ledger, minimo_turnos=3) == {}


def test_pacientes_en_riesgo_de_fuga_zona_intermedia():
    ledger = {
        "en_riesgo": [_ev("2025-10", "turno_asistido")],   # 6 meses antes de 2026-04
        "activo": [_ev("2026-03", "turno_asistido")],       # 1 mes antes
        "ya_inactivo": [_ev("2024-01", "turno_asistido")],  # >14 meses antes
    }
    riesgo = mp.pacientes_en_riesgo_de_fuga(ledger, periodo_actual="2026-04")
    assert riesgo == ["en_riesgo"]


def test_porcentaje_base_inactiva():
    ledger = {
        "activo": [_ev("2026-04", "turno_asistido")],
        "inactivo1": [_ev("2024-01", "turno_asistido")],
        "inactivo2": [_ev("2023-01", "turno_asistido")],
        "inactivo3": [_ev("2022-01", "turno_asistido")],
    }
    assert mp.porcentaje_base_inactiva(ledger, periodo_actual="2026-04") == 75.0


def test_dias_desde_ultimo_contacto_aproxima_por_mes():
    ledger = {"x": [_ev("2026-01", "turno_asistido")]}
    dias = mp.dias_desde_ultimo_contacto(ledger, periodo_actual="2026-04")
    assert dias["x"] == round(3 * 30.4)


# ---------------------------------------------------------------------------
# Valor y concentración
# ---------------------------------------------------------------------------

def test_ltv_real_suma_solo_eventos_de_pago():
    ledger = {"x": [_ev("2026-01", "pago", monto=1000), _ev("2026-02", "pago", monto=2000),
                    _ev("2026-02", "presupuesto_emitido", monto=999999)]}
    assert mp.ltv_real(ledger) == {"x": 3000}


def test_ticket_promedio_por_cliente():
    ledger = {"x": [_ev("2026-01", "pago", monto=1000), _ev("2026-02", "pago", monto=3000)]}
    assert mp.ticket_promedio_por_cliente(ledger) == {"x": 2000.0}


def test_concentracion_ingresos_detecta_riesgo_aunque_el_promedio_sea_sano():
    ledger = {}
    # 3 pacientes "ballena" con el grueso de la facturación...
    for i, monto in enumerate([800000, 700000, 500000]):
        ledger[f"ballena{i}"] = [_ev("2026-01", "pago", monto=monto)]
    # ...y 7 pacientes chicos que mantienen el promedio general "sano".
    for i in range(7):
        ledger[f"chico{i}"] = [_ev("2026-01", "pago", monto=10000)]

    resultado = mp.concentracion_ingresos(ledger, top_pct=0.30)
    assert resultado["n_pacientes_top"] == 3
    assert resultado["share_ingresos"] > 0.9
    assert set(resultado["pacientes_top"]) == {"ballena0", "ballena1", "ballena2"}


def test_mix_tratamientos_por_paciente():
    ledger = {"x": [
        _ev("2026-01", "presupuesto_aceptado", tratamiento="Ortodoncia"),
        _ev("2026-02", "presupuesto_aceptado", tratamiento="Ortodoncia"),
        _ev("2026-03", "presupuesto_aceptado", tratamiento="Blanqueamiento"),
    ]}
    assert mp.mix_tratamientos_por_paciente(ledger) == {"x": {"Ortodoncia": 2, "Blanqueamiento": 1}}


# ---------------------------------------------------------------------------
# Ciclo de vida
# ---------------------------------------------------------------------------

def test_retencion_por_cohorte_alta():
    ledger = {
        "retenido": [_ev("2026-01", "alta"), _ev("2026-06", "turno_asistido")],
        "perdido": [_ev("2026-01", "alta")],
    }
    assert mp.retencion_por_cohorte_alta(ledger) == {"2026-01": 50.0}


def test_intervalo_medio_entre_visitas():
    ledger = {"x": [_ev("2026-01", "turno_asistido"), _ev("2026-03", "turno_asistido"), _ev("2026-06", "turno_asistido")]}
    # brechas: 2 meses (ene->mar), 3 meses (mar->jun) -> promedio 2.5
    assert mp.intervalo_medio_entre_visitas(ledger) == {"x": 2.5}


def test_intervalo_medio_requiere_al_menos_dos_visitas():
    ledger = {"x": [_ev("2026-01", "turno_asistido")]}
    assert mp.intervalo_medio_entre_visitas(ledger) == {}


def test_abandono_a_mitad_tratamiento():
    ledger = {
        "abandono": [_ev("2026-01", "tratamiento_iniciado")],
        "completo": [_ev("2026-01", "tratamiento_iniciado"), _ev("2026-03", "tratamiento_completado")],
    }
    assert mp.abandono_a_mitad_tratamiento(ledger) == ["abandono"]


# ---------------------------------------------------------------------------
# Atribución
# ---------------------------------------------------------------------------

def test_nuevos_vs_recurrentes():
    ledger = {
        "nuevo": [_ev("2026-04", "turno_asistido")],
        "recurrente": [_ev("2026-01", "turno_asistido"), _ev("2026-04", "turno_asistido")],
        "sin_actividad_este_mes": [_ev("2026-02", "turno_asistido")],
    }
    assert mp.nuevos_vs_recurrentes(ledger, "2026-04") == {"nuevos": 1, "recurrentes": 1}


def test_atribucion_referidos():
    ledger = {"x": [_ev("2026-01", "referido_recibido"), _ev("2026-02", "referido_recibido")], "y": [_ev("2026-01", "pago", 100)]}
    assert mp.atribucion_referidos(ledger) == {"x": 2}


# ---------------------------------------------------------------------------
# Agregadas
# ---------------------------------------------------------------------------

def test_tasa_segunda_visita():
    ledger = {
        "vuelve": [_ev("2026-01", "turno_asistido"), _ev("2026-02", "turno_asistido")],
        "no_vuelve": [_ev("2026-01", "turno_asistido")],
    }
    assert mp.tasa_segunda_visita(ledger) == 50.0


def test_velocidad_presupuesto_a_aceptacion():
    ledger = {"x": [_ev("2026-01", "presupuesto_emitido"), _ev("2026-03", "presupuesto_aceptado")]}
    assert mp.velocidad_presupuesto_a_aceptacion(ledger) == {"x": 2.0}


def test_multi_tratamiento_vs_mono():
    ledger = {
        "multi": [_ev("2026-01", "pago", tratamiento="A"), _ev("2026-02", "pago", tratamiento="B")],
        "mono": [_ev("2026-01", "pago", tratamiento="A")],
    }
    resultado = mp.multi_tratamiento_vs_mono(ledger)
    assert resultado == {"multi_tratamiento_pct": 50.0, "mono_tratamiento_pct": 50.0}


def test_estacionalidad_observada_por_paciente():
    ledger = {
        "x": [_ev("2026-01", "turno_no_show"), _ev("2025-01", "turno_no_show")],
        "y": [_ev("2026-07", "turno_no_show")],
    }
    assert mp.estacionalidad_observada_por_paciente(ledger) == {"01": 2, "07": 1}


# ---------------------------------------------------------------------------
# Sin datos transaccionales
# ---------------------------------------------------------------------------

def test_ledger_vacio_no_rompe_ninguna_metrica():
    resultado = mp.calcular_todas({})
    assert resultado["no_show_recurrente"] == {}
    assert resultado["ltv_real"] == {}
    assert resultado["concentracion_ingresos"] is None
    assert resultado["porcentaje_base_inactiva"] is None
    assert resultado["tasa_segunda_visita"] is None
    assert resultado["nuevos_vs_recurrentes"] is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
