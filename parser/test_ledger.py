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


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
