"""
test_guia_diagnostico.py

Sin pytest: corre con `python -m parser.diagnostico.test_guia_diagnostico`.

Cubre el catálogo de las 55 preguntas de la Guía de Diagnóstico y el
flag `requerida_diagnostico` (Núcleo + las de Contexto con consumidor
real en el pipeline) — sin llamar a la API.
"""

from parser.diagnostico.guia_diagnostico import GUIA_DIAGNOSTICO, PREGUNTAS_REQUERIDAS_ONBOARDING


def test_catalogo_tiene_las_55_preguntas_del_docx():
    # 53 originales + P9b y P21b agregadas (ver README.md).
    assert len(GUIA_DIAGNOSTICO) == 55


def test_cada_pregunta_del_dict_se_referencia_a_si_misma():
    # Bug fácil de cometer al copiar/pegar _pregunta(...): que la key del
    # dict no coincida con el id real de la PreguntaGuia.
    for id_, pregunta in GUIA_DIAGNOSTICO.items():
        assert pregunta.id == id_, f"key {id_!r} no coincide con pregunta.id {pregunta.id!r}"


def test_las_25_preguntas_nucleo_son_requeridas():
    # Núcleo (bloques 1, 2, 4 y 10 del docx) siempre tiene que pedirse en
    # el onboarding, sin excepción.
    nucleo = [p for p in GUIA_DIAGNOSTICO.values() if p.nucleo]
    assert len(nucleo) == 25
    assert all(p.requerida_diagnostico for p in nucleo)


def test_p51_es_requerida_aunque_sea_contexto_por_estacionalidad_py():
    # P51 es Contexto (bloque 11), pero estacionalidad.py la chequea
    # directo (`respuestas.get("P51", "")`) — si esto da False, el
    # onboarding web apagaría esa función en silencio para todo cliente.
    p51 = GUIA_DIAGNOSTICO["P51"]
    assert p51.nucleo is False
    assert p51.requerida_diagnostico is True


def test_documentacion_bloque_3_queda_registrada_pero_no_requerida():
    # P15-P18 (historia clínica/consentimientos): ningún módulo del
    # pipeline las lee hoy — quedan en el catálogo, pero el onboarding
    # web no las pregunta.
    for id_ in ("P15", "P16", "P17", "P18"):
        pregunta = GUIA_DIAGNOSTICO[id_]
        assert pregunta.nucleo is False
        assert pregunta.requerida_diagnostico is False


def test_p31_p35_p39_tampoco_son_requeridas():
    # Únicas de sus bloques (6, 7, 8) sin consumidor real: proveedores,
    # capacitación, conversión de consulta a turno.
    for id_ in ("P31", "P35", "P39"):
        assert GUIA_DIAGNOSTICO[id_].requerida_diagnostico is False


def test_requeridas_para_onboarding_son_48_de_55():
    # 25 Núcleo + 23 de Contexto con consumidor real en el pipeline
    # (contexto_cualitativo.py / diagnostico.py / catalogo_tecnologico.py).
    assert len(PREGUNTAS_REQUERIDAS_ONBOARDING) == 48
    assert len(GUIA_DIAGNOSTICO) - len(PREGUNTAS_REQUERIDAS_ONBOARDING) == 7


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
