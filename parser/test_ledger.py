"""
test_ledger.py

Sin pytest: corre con `python3 test_ledger.py`.
Cubre construir_ledger_pacientes: que resuelva identidad vía matching.py
(no el nombre crudo), que descarte filas sin nombre o fecha en vez de
inventar, y que el resultado quede ordenado cronológicamente por paciente.
"""

from ledger import construir_ledger_pacientes
from matching import RegistroClientes


def test_variantes_del_mismo_nombre_terminan_en_el_mismo_paciente():
    registros = [
        {"paciente": "Juan Perez", "fecha": "2026-01", "tipo_evento": "pago", "monto": 50000},
        {"paciente": "J. Perez", "fecha": "2026-02", "tipo_evento": "pago", "monto": 30000},
    ]
    ledger, _ = construir_ledger_pacientes(registros)
    assert len(ledger) == 1, f"esperaba un solo paciente, dio {len(ledger)}"
    eventos = list(ledger.values())[0]
    assert len(eventos) == 2
    assert sum(e["monto"] for e in eventos) == 80000


def test_registros_sin_nombre_o_sin_fecha_se_descartan():
    registros = [
        {"paciente": "Juan Perez", "fecha": "2026-01", "tipo_evento": "pago", "monto": 1000},
        {"paciente": "", "fecha": "2026-01", "tipo_evento": "pago", "monto": 999},
        {"paciente": "Pedro Gomez", "fecha": None, "tipo_evento": "pago", "monto": 999},
        {"paciente": "Ana Torres", "fecha": "no es una fecha", "tipo_evento": "pago", "monto": 999},
    ]
    ledger, _ = construir_ledger_pacientes(registros)
    assert len(ledger) == 1
    montos = [e["monto"] for eventos in ledger.values() for e in eventos]
    assert montos == [1000]


def test_eventos_quedan_ordenados_cronologicamente():
    registros = [
        {"paciente": "Juan Perez", "fecha": "2026-03", "tipo_evento": "turno_asistido"},
        {"paciente": "Juan Perez", "fecha": "2026-01", "tipo_evento": "turno_asistido"},
        {"paciente": "Juan Perez", "fecha": "2026-02", "tipo_evento": "turno_no_show"},
    ]
    ledger, _ = construir_ledger_pacientes(registros)
    periodos = [e["periodo"] for eventos in ledger.values() for e in eventos]
    assert periodos == ["2026-01", "2026-02", "2026-03"]


def test_registro_clientes_se_puede_reusar_entre_llamadas():
    registro = RegistroClientes()
    ledger1, _ = construir_ledger_pacientes(
        [{"paciente": "Juan Perez", "fecha": "2026-01", "tipo_evento": "pago", "monto": 100}],
        registro_clientes=registro,
    )
    ledger2, _ = construir_ledger_pacientes(
        [{"paciente": "J. Perez", "fecha": "2026-02", "tipo_evento": "pago", "monto": 200}],
        registro_clientes=registro,
    )
    assert set(ledger1.keys()) == set(ledger2.keys()), "el mismo paciente en dos llamadas debe dar el mismo ID"


def test_sin_registros_da_ledger_vacio():
    ledger, registro = construir_ledger_pacientes([])
    assert ledger == {}
    assert registro.clientes == {}


# ---------------------------------------------------------------------------
# Fase H4a: campo_es_id_estable — evita el matching difuso cuando la columna
# de paciente ya es un identificador canónico, no un nombre tipeado a mano.
# ---------------------------------------------------------------------------

def test_ids_estables_no_se_fusionan_por_matching_difuso():
    """El caso real del bug: "Paciente 1"/"Paciente 2"/"Paciente 3" pasan
    el umbral de fusión automática de matching.py (comparten el primer
    token + similitud > 0.80) y HOY se fusionan en un solo cliente. Con
    campo_es_id_estable=True eso no puede pasar — cada valor de columna
    es su propio cliente_id, sin pasar por matching.py."""
    registros = [
        {"paciente": "Paciente 1", "fecha": "2026-01", "tipo_evento": "pago", "monto": 100},
        {"paciente": "Paciente 2", "fecha": "2026-01", "tipo_evento": "pago", "monto": 200},
        {"paciente": "Paciente 3", "fecha": "2026-01", "tipo_evento": "pago", "monto": 300},
    ]
    ledger, _ = construir_ledger_pacientes(registros, campo_es_id_estable=True)
    assert len(ledger) == 3, f"esperaba 3 pacientes distintos, dio {len(ledger)}"


def test_mismo_id_estable_en_dos_filas_agrupa_igual():
    """Sin fusión difusa de por medio, dos filas con el MISMO id literal
    siguen agrupando en el mismo paciente — no es que se vuelvan todas
    distintas, es que dejan de fusionarse cuando NO deberían."""
    registros = [
        {"paciente": "P1045", "fecha": "2026-01", "tipo_evento": "pago", "monto": 100},
        {"paciente": "P1045", "fecha": "2026-02", "tipo_evento": "pago", "monto": 200},
        {"paciente": "P1011", "fecha": "2026-01", "tipo_evento": "pago", "monto": 999},
    ]
    ledger, _ = construir_ledger_pacientes(registros, campo_es_id_estable=True)
    assert len(ledger) == 2
    assert sum(e["monto"] for e in ledger["P1045"]) == 300


def test_sin_id_estable_los_nombres_reales_se_siguen_fusionando_igual():
    """No-regresión: el default (False) no cambia el camino de nombres
    reales — "Juan Perez"/"J. Perez" se siguen fusionando vía
    matching.py, exactamente como antes de esta fase."""
    registros = [
        {"paciente": "Juan Perez", "fecha": "2026-01", "tipo_evento": "pago", "monto": 50000},
        {"paciente": "J. Perez", "fecha": "2026-02", "tipo_evento": "pago", "monto": 30000},
    ]
    ledger, _ = construir_ledger_pacientes(registros)  # campo_es_id_estable default False
    assert len(ledger) == 1


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
