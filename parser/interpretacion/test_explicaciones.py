"""
test_explicaciones.py

Sin pytest: corre con `python -m parser.interpretacion.test_explicaciones`.

Cada test usa el motivo TÉCNICO EXACTO que validacion.py produce hoy
(copiado literal, no reconstruido) — si validacion.py cambia el texto,
este test lo detecta.
"""

from parser.interpretacion.explicaciones import explicar_cuarentena, explicar_derivada, explicar_discrepancia, nombre_humano
from parser.cobertura_calidad.validacion import validar_forma, validar_identidades, validar_origen, validar_tipo


def test_nombre_humano_usa_metricas_con_fallback():
    assert nombre_humano("no_shows") != "no_shows"  # tiene nombre_humano declarado
    assert nombre_humano("variable_que_no_existe") == "variable_que_no_existe"  # fallback


def test_motivo_no_reconocido_se_muestra_tal_cual():
    info = {"motivo": "un motivo inventado que no matchea ningún patrón"}
    assert explicar_cuarentena("no_shows", info) == info["motivo"]


# ---------------------------------------------------------------------------
# Cada patrón de validacion.py, con el motivo EXACTO que esa función arma hoy
# ---------------------------------------------------------------------------

def test_dict_esperado():
    motivo = validar_tipo("ingreso_por_paciente", 1240)
    assert motivo is not None
    texto = explicar_cuarentena("ingreso_por_paciente", {"motivo": motivo})
    assert "desglosado por categoría" in texto
    assert "un solo número" in texto
    assert "jerga" not in texto  # no se cuela nada técnico nuevo


def test_list_esperado():
    motivo = validar_tipo("tareas_sin_backup", 4)
    assert motivo is not None
    texto = explicar_cuarentena("tareas_sin_backup", {"motivo": motivo})
    assert "lista de elementos" in texto


def test_ledger_esperado_llego_int():
    """El caso literal que reportó Felipe: 'se esperaba ledger (dict de
    listas), llegó int' con el valor 1240."""
    motivo = validar_tipo("ledger_pacientes", 1240)
    assert motivo == "se esperaba ledger (dict de listas), llegó int"
    texto = explicar_cuarentena("ledger_pacientes", {"motivo": motivo})
    assert "historial por paciente" in texto
    assert "dict de listas" not in texto  # la jerga no debe sobrevivir a la traducción


def test_ledger_valor_no_es_lista():
    motivo = validar_tipo("ledger_pacientes", {"P1": [{}], "P2": 5})
    assert motivo is not None
    texto = explicar_cuarentena("ledger_pacientes", {"motivo": motivo})
    assert "historial por paciente" in texto


def test_numero_esperado():
    motivo = validar_tipo("no_shows", "cuarenta")
    assert motivo is not None
    texto = explicar_cuarentena("no_shows", {"motivo": motivo})
    assert "tiene que ser un número" in texto


def test_valor_negativo():
    motivo = validar_forma("no_shows", -5)
    assert motivo is not None
    texto = explicar_cuarentena("no_shows", {"motivo": motivo})
    assert "negativo" in texto
    assert "-5" in texto


def test_fraccion_travestida_de_conteo():
    motivo = validar_forma("no_shows", 0.22)
    assert motivo is not None
    texto = explicar_cuarentena("no_shows", {"motivo": motivo})
    assert "0.22" in texto
    assert "columna de tasa" in texto
    assert "hallazgo 1.3" not in texto  # la referencia interna no debe sobrevivir


def test_variable_interna():
    motivo = validar_origen("automatizaciones_activas", "migracion_excel:Hoja1")
    assert motivo is not None
    texto = explicar_cuarentena("automatizaciones_activas", {"motivo": motivo})
    assert "calcula el sistema" in texto
    assert "migracion_excel:Hoja1" in texto


def test_identidad_violada():
    rechazos = validar_identidades({"no_shows": 100, "turnos_agendados": 50})
    assert len(rechazos) == 1
    texto = explicar_cuarentena("no_shows", {"motivo": rechazos[0].motivo})
    assert "100" in texto and "50" in texto
    assert "no puede ser más que" in texto


def test_reemplazada_por_derivacion_no_se_muestra_como_error():
    info = {
        "motivo": "se esperaba número, llegó str — reemplazada por un valor derivado de la tasa",
        "reemplazada_por_derivacion": True,
    }
    texto = explicar_cuarentena("no_shows", info)
    assert "ya está resuelto" in texto
    assert "reemplazada por un valor derivado" not in texto  # no repite el motivo técnico


def test_discrepancia_interpola_numeros_reales():
    info = {
        "motivo": "la tasa declarada en la planilla no coincide con lo calculado a partir de esta variable (ver discrepancias_reconciliacion)",
        "discrepancia": {"kpi_id": 4, "kpi_nombre": "Tasa de no-show", "calculado": 28.9, "declarado": 22.4},
    }
    texto = explicar_cuarentena("no_shows", info)
    assert "22.4" in texto
    assert "28.9" in texto
    assert "Tasa de no-show" in texto
    assert "discrepancias_reconciliacion" not in texto  # no repite la referencia a la clave del payload


# ---------------------------------------------------------------------------
# Derivadas y discrepancias (fuera de la cuarentena)
# ---------------------------------------------------------------------------

def test_explicar_derivada():
    d = {
        "variable": "no_shows", "valor": 53.0, "kpi_id": 4, "kpi_nombre": "Tasa de no-show",
        "desde_denominador": "turnos_agendados", "tasa_declarada": 22.0,
    }
    texto = explicar_derivada(d)
    assert "53" in texto
    assert "22" in texto
    assert "Tasa de no-show" in texto
    assert "sugerencia a confirmar" in texto


def test_explicar_derivada_sin_kpi_nombre_no_rompe():
    d = {
        "variable": "no_shows", "valor": 53.0, "kpi_id": 999, "kpi_nombre": None,
        "desde_denominador": "turnos_agendados", "tasa_declarada": 22.0,
    }
    texto = explicar_derivada(d)
    assert "KPI 999" in texto


def test_explicar_discrepancia():
    d = {
        "kpi_id": 4, "kpi_nombre": "Tasa de no-show", "calculado": 28.9, "declarado": 22.4,
        "variables": ["no_shows", "turnos_agendados"],
    }
    texto = explicar_discrepancia(d)
    assert "22.4" in texto and "28.9" in texto
    assert "Tasa de no-show" in texto


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
