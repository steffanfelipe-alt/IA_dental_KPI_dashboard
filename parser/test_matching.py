"""
test_matching.py

Sin pytest: corre con `python3 test_matching.py`.
Cubre la Fase 2 del plan de evolución: resolución de identidad de
pacientes (matching.py) — el motor de similitud, la banda gris de
decisión, y el caso real que motivó no confiar en un solo fuzzy score
(ver docstring de matching.py: "Juan Pérez" vs "Juana Pérez").
"""

from matching import (
    RegistroClientes,
    _nombres_de_pila_compatibles,
    _similitud_bruta,
    encontrar_o_crear_cliente,
    normalizar_nombre,
    resolver_lote,
)


def test_variantes_obvias_del_mismo_nombre_dan_un_solo_id():
    registro = RegistroClientes()
    m1 = encontrar_o_crear_cliente("Juan Pérez", registro)
    m2 = encontrar_o_crear_cliente("J. Perez", registro)
    m3 = encontrar_o_crear_cliente("JUAN PEREZ", registro)
    assert m1.cliente_id == m2.cliente_id == m3.cliente_id
    assert m2.zona == "fusion_automatica"
    assert m3.zona == "fusion_automatica"


def test_apellido_compuesto_fusiona_automatico_gracias_a_rapidfuzz():
    # El caso que motivó usar rapidfuzz en vez de solo difflib: un
    # apellido compuesto no debería quedar como una persona aparte.
    registro = RegistroClientes()
    m1 = encontrar_o_crear_cliente("Juan Pérez Gómez", registro)
    m2 = encontrar_o_crear_cliente("Juan Pérez", registro)
    assert m1.cliente_id == m2.cliente_id
    assert m2.zona == "fusion_automatica"


def test_juan_y_juana_no_se_fusionan_solos_aunque_el_score_bruto_sea_alto():
    # El hallazgo real: token_set_ratio da ~95% para estos dos nombres,
    # por encima de cualquier umbral ingenuo de fusión automática — y son
    # personas distintas. No deben terminar con el mismo ID sin que el
    # dueño confirme.
    bruto = _similitud_bruta(normalizar_nombre("Juan Perez"), normalizar_nombre("Juana Perez"))
    assert bruto > 0.90, f"se esperaba un score bruto engañosamente alto, dio {bruto}"

    registro = RegistroClientes()
    m1 = encontrar_o_crear_cliente("Juan Perez", registro)
    m2 = encontrar_o_crear_cliente("Juana Perez", registro)
    assert m1.cliente_id != m2.cliente_id, "Juan y Juana Perez no son la misma persona"
    assert m2.zona == "zona_gris", f"esperaba zona_gris, dio {m2.zona!r} (similitud={m2.similitud})"


def test_personas_claramente_distintas_no_generan_ni_conflicto():
    registro = RegistroClientes()
    m1 = encontrar_o_crear_cliente("Juan Perez", registro)
    m2 = encontrar_o_crear_cliente("Pedro Gomez", registro)
    assert m1.cliente_id != m2.cliente_id
    assert m2.zona == "nuevo"


def test_nombres_de_pila_compatibles_regla_de_iniciales():
    assert _nombres_de_pila_compatibles("JUAN", "JUAN")
    assert _nombres_de_pila_compatibles("J", "JUAN")
    assert _nombres_de_pila_compatibles("JUAN", "J")
    assert not _nombres_de_pila_compatibles("JUAN", "JUANA")
    assert not _nombres_de_pila_compatibles("MARCO", "MARCOS")


def test_zona_gris_no_fusiona_y_queda_disponible_para_conflictos_pendientes():
    asignaciones, ambiguos, _ = resolver_lote([
        ("Juan Perez", "2026-04"),
        ("Juana Perez", "2026-04"),
    ])
    assert asignaciones[0] != asignaciones[1]
    assert len(ambiguos) == 1
    assert ambiguos[0]["nombre"] == "Juana Perez"
    assert ambiguos[0]["candidato_existente"] == "Juan Perez"


def test_resolver_lote_reusa_registro_entre_llamadas():
    # Simula dos archivos migrados en momentos distintos: el segundo debe
    # poder fusionar contra lo que ya quedó resuelto del primero.
    _, _, registro = resolver_lote([("Juan Perez", "2026-03")])
    asignaciones2, _, _ = resolver_lote([("J. Perez", "2026-04")], registro)
    assert asignaciones2[0] in registro.clientes


def test_normalizar_nombre_quita_titulos_acentos_y_mayusculas():
    assert normalizar_nombre("Dra. María José Pérez") == normalizar_nombre("MARIA JOSE PEREZ")
    assert normalizar_nombre("  Juan   Perez  ") == "JUAN PEREZ"


def test_similitud_bruta_veredicto_coincide_entre_motores_en_casos_claros():
    # No exigimos el mismo score exacto entre rapidfuzz y el fallback
    # difflib (son algoritmos distintos) — sí que ambos concuerden en los
    # casos inequívocos: idéntico, y totalmente distinto.
    import difflib as _difflib
    a, b = normalizar_nombre("Juan Perez"), normalizar_nombre("Juan Perez")
    assert _similitud_bruta(a, b) == 1.0
    assert _difflib.SequenceMatcher(None, a, b).ratio() == 1.0

    a, b = normalizar_nombre("Juan Perez"), normalizar_nombre("Pedro Gomez")
    assert _similitud_bruta(a, b) < 0.5
    assert _difflib.SequenceMatcher(None, a, b).ratio() < 0.5


def test_nombre_vacio_no_rompe_similitud():
    assert _similitud_bruta("", "JUAN PEREZ") == 0.0


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
