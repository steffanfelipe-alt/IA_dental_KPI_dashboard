"""
test_cruces_propuestos.py

Sin pytest, sin red (el "cliente" es un stub que devuelve texto fijo, no
llama a ningún servicio): corre con `python -m parser.catalogo.test_cruces_propuestos`.
Fase C del plan de evolución — capa 3 de cruces.py, propuestas del modelo
validadas por los mismos guardarraíles deterministas de la capa 1/2.
"""

import json

from parser.cobertura_calidad.coverage import VariableValue
from parser.catalogo.cruces_propuestos import CONFIANZA_PROPUESTA, MAX_PROPUESTAS, proponer_cruces


def _vv(valor, confianza=0.9, serie=None):
    return VariableValue(valor, "migracion_excel", confianza, serie=serie)


SERIE = {"2026-01": 100.0, "2026-02": 110.0, "2026-03": 120.0}
SERIE_B = {"2026-01": 10.0, "2026-02": 11.0, "2026-03": 12.0}


class _Bloque:
    def __init__(self, texto):
        self.type, self.text = "text", texto


class _ClienteFalso:
    """Stub de anthropic.Anthropic — no llama a ninguna API, sólo devuelve
    el texto que se le configuró y registra si fue invocado (para poder
    verificar que ciertos casos NUNCA llaman al cliente)."""
    def __init__(self, texto_respuesta: str):
        self.texto_respuesta = texto_respuesta
        self.llamadas = 0

        class _Messages:
            def create(_self, **kwargs):
                self.llamadas += 1
                return type("Respuesta", (), {
                    "content": [_Bloque(self.texto_respuesta)],
                    "stop_reason": "end_turn",
                })()
        self.messages = _Messages()


def _propuesta_json(propuestas: list[dict]) -> str:
    return json.dumps({"propuestas": propuestas}, ensure_ascii=False)


def _variables_monto_y_conteo():
    return {
        "monto_cobrado": _vv(120.0, serie=SERIE),
        "turnos_asistidos": _vv(12.0, serie=SERIE_B),
    }


def test_propuesta_valida_se_acepta():
    propuestas = [{
        "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "turnos_asistidos",
        "unidad_esperada": "monto_ars/unidad",
        "etapa_embudo": "turnos asistidos",
        "como_ayuda_decision": "ingreso promedio por paciente asistido",
    }]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=cliente)

    assert len(cruces) == 1
    c = cruces[0]
    assert c.variable_a == "monto_cobrado" and c.variable_b == "turnos_asistidos"
    assert c.origen == "propuesto"
    assert c.valor == round(120.0 / 12.0, 2)
    assert "Propuesto por el modelo" in c.justificacion
    assert "ingreso promedio por paciente asistido" in c.justificacion
    assert c.etapa_embudo == "turnos asistidos"
    assert c.impacto_decision == "ingreso promedio por paciente asistido"


def test_unidad_declarada_que_no_coincide_con_el_algebra_se_descarta():
    """El modelo dice "%" para un monto ÷ conteo, que en realidad da
    "monto_ars/unidad" — la propuesta se descarta aunque el par de
    variables sea dimensionalmente legal."""
    propuestas = [{
        "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "turnos_asistidos",
        "unidad_esperada": "%",  # incorrecto a propósito
        "por_que_le_importa_al_negocio": "...",
    }]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=cliente)
    assert cruces == []


def test_variable_inexistente_se_descarta():
    propuestas = [{
        "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "variable_que_no_existe",
        "unidad_esperada": "monto_ars/unidad", "por_que_le_importa_al_negocio": "...",
    }]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=cliente)
    assert cruces == []


def test_variable_en_cuarentena_se_descarta():
    """Una variable en cuarentena nunca llega al dict `variables` que
    recibe proponer_cruces (pipeline.py la filtra antes) — el modelo
    puede nombrarla igual (no sabe que está en cuarentena) y el mismo
    chequeo de "no está en variables" la descarta."""
    propuestas = [{
        "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "no_shows",  # no_shows no está en el dict
        "unidad_esperada": "monto_ars/unidad", "por_que_le_importa_al_negocio": "...",
    }]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=cliente)  # no_shows ausente a propósito
    assert cruces == []


def test_conteo_dividido_conteo_fuera_del_embudo_se_descarta():
    """no_shows y resenas_nuevas son ambos conteo pero ninguno está en
    ETAPAS_EMBUDO — conteo÷conteo fuera del embudo es exclusivo de la
    capa 1 (generar_cruces_embudo), la capa 3 no lo acepta tampoco."""
    variables = {
        "no_shows": _vv(3.0, serie={"2026-01": 3.0, "2026-02": 4.0}),
        "resenas_nuevas": _vv(5.0, serie={"2026-01": 5.0, "2026-02": 6.0}),
    }
    propuestas = [{
        "variable_a": "no_shows", "operacion": "/", "variable_b": "resenas_nuevas",
        "unidad_esperada": "%", "por_que_le_importa_al_negocio": "...",
    }]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(variables, client=cliente)
    assert cruces == []


def test_conteo_dividido_conteo_dentro_del_embudo_se_acepta():
    """Caso positivo del anterior: turnos_asistidos y consultas_nuevas_mes
    SÍ están en ETAPAS_EMBUDO y respetan el orden — debe aceptarse."""
    variables = {
        "turnos_asistidos": _vv(59.0, serie={"2026-01": 51.0, "2026-02": 48.0, "2026-03": 62.0}),
        "consultas_nuevas_mes": _vv(105.0, serie={"2026-01": 95.0, "2026-02": 88.0, "2026-03": 110.0}),
    }
    propuestas = [{
        "variable_a": "turnos_asistidos", "operacion": "/", "variable_b": "consultas_nuevas_mes",
        "unidad_esperada": "%", "por_que_le_importa_al_negocio": "conversion del embudo",
    }]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(variables, client=cliente)
    assert len(cruces) == 1
    assert cruces[0].unidad == "%"


def test_json_malformado_no_rompe_el_pipeline():
    cliente = _ClienteFalso("esto no es JSON en absoluto {{{")
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=cliente)
    assert cruces == []


def test_json_envuelto_en_fence_markdown_se_parsea_igual():
    propuestas = [{
        "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "turnos_asistidos",
        "unidad_esperada": "monto_ars/unidad", "por_que_le_importa_al_negocio": "...",
    }]
    texto_con_fence = "```json\n" + _propuesta_json(propuestas) + "\n```"
    cliente = _ClienteFalso(texto_con_fence)
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=cliente)
    assert len(cruces) == 1


def test_operacion_invalida_se_descarta():
    propuestas = [{
        "variable_a": "monto_cobrado", "operacion": "*", "variable_b": "turnos_asistidos",
        "unidad_esperada": "monto_ars/unidad", "por_que_le_importa_al_negocio": "...",
    }]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=cliente)
    assert cruces == []


def test_confianza_tiene_techo_aunque_los_insumos_confien_mucho():
    variables = {
        "monto_cobrado": _vv(120.0, confianza=0.95, serie=SERIE),
        "turnos_asistidos": _vv(12.0, confianza=0.95, serie=SERIE_B),
    }
    propuestas = [{
        "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "turnos_asistidos",
        "unidad_esperada": "monto_ars/unidad", "por_que_le_importa_al_negocio": "...",
    }]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(variables, client=cliente)
    assert cruces[0].confianza == CONFIANZA_PROPUESTA, "nunca por encima del techo, aunque los insumos confíen 0.95"


def test_client_none_no_llama_a_nada_y_devuelve_vacio():
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=None)
    assert cruces == []


def test_menos_de_dos_variables_con_serie_no_llama_al_cliente():
    """Con una sola variable útil no hay con qué cruzar — no tiene sentido
    gastar una llamada a la API para que el modelo no proponga nada."""
    variables = {"monto_cobrado": _vv(120.0, serie=SERIE)}
    cliente = _ClienteFalso(_propuesta_json([]))
    cruces = proponer_cruces(variables, client=cliente)
    assert cruces == []
    assert cliente.llamadas == 0, "no debía llamar a la API con menos de 2 variables útiles"


def test_respeta_el_maximo_de_propuestas():
    """MAX_PROPUESTAS trunca el batch ANTES de validar, no depende de que
    todas sean válidas para probarlo — con más de 8 propuestas idénticas
    válidas, sólo se procesan las primeras 8."""
    propuesta_valida = {
        "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "turnos_asistidos",
        "unidad_esperada": "monto_ars/unidad", "por_que_le_importa_al_negocio": "...",
    }
    cliente = _ClienteFalso(_propuesta_json([propuesta_valida] * (MAX_PROPUESTAS + 5)))
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=cliente)
    assert len(cruces) == MAX_PROPUESTAS


def test_propuesta_sin_suficientes_periodos_comunes_se_descarta():
    """La propuesta pasa la validación de unidades pero calcular_cruce
    rechaza por no llegar al mínimo de períodos comunes — mismo
    guardarraíl que las capas 1/2, reusado sin reimplementar nada."""
    variables = {
        "monto_cobrado": _vv(120.0, serie={"2026-01": 120.0}),  # 1 solo período
        "turnos_asistidos": _vv(12.0, serie={"2026-01": 12.0}),
    }
    propuestas = [{
        "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "turnos_asistidos",
        "unidad_esperada": "monto_ars/unidad", "por_que_le_importa_al_negocio": "...",
    }]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(variables, client=cliente)
    assert cruces == []


# ---------------------------------------------------------------------------
# Fase F: etapa_embudo / como_ayuda_decision — el modelo ya no manda un solo
# texto libre ("por_que_le_importa_al_negocio"), manda dos campos
# estructurados para que la UI los muestre por separado en la tarjeta de
# aceptar/descartar de cada cruce propuesto.
# ---------------------------------------------------------------------------

def test_etapa_y_decision_faltantes_no_descartan_la_propuesta():
    """Prosa incompleta del modelo no es motivo para tirar un cruce
    dimensionalmente válido — cae a un placeholder, no a cruces vacío."""
    propuestas = [{
        "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "turnos_asistidos",
        "unidad_esperada": "monto_ars/unidad",
        # sin "etapa_embudo" ni "como_ayuda_decision" a propósito
    }]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=cliente)
    assert len(cruces) == 1
    c = cruces[0]
    assert c.etapa_embudo == "(el modelo no especificó una etapa)"
    assert c.impacto_decision == "(el modelo no explicó el impacto en la decisión)"
    assert c.etapa_embudo in c.justificacion
    assert c.impacto_decision in c.justificacion


def test_null_en_los_campos_de_prosa_no_tira_abajo_el_lote():
    """El modelo puede mandar `null` (o un número) donde se esperaba texto.
    Eso no puede romper el batch entero: un `.strip()` sobre None se
    llevaría puestas TODAS las propuestas, no sólo la mal formada. La
    segunda propuesta acá es válida y debe sobrevivir igual."""
    propuestas = [
        {
            "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "turnos_asistidos",
            "unidad_esperada": "monto_ars/unidad",
            "etapa_embudo": None, "como_ayuda_decision": 42,  # tipos inesperados a propósito
        },
        {
            "variable_a": "monto_cobrado", "operacion": "/", "variable_b": "turnos_asistidos",
            "unidad_esperada": "monto_ars/unidad",
            "etapa_embudo": "turnos asistidos", "como_ayuda_decision": "ticket promedio real",
        },
    ]
    cliente = _ClienteFalso(_propuesta_json(propuestas))
    cruces = proponer_cruces(_variables_monto_y_conteo(), client=cliente)
    assert len(cruces) == 2, "la propuesta mal tipada cae al placeholder, no rompe el lote"
    assert cruces[0].etapa_embudo == "(el modelo no especificó una etapa)"
    assert cruces[0].impacto_decision == "(el modelo no explicó el impacto en la decisión)"
    assert cruces[1].etapa_embudo == "turnos asistidos"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
