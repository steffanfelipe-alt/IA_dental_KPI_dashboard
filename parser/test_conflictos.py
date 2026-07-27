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


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
