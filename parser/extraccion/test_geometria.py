"""
test_geometria.py

Sin pytest: corre con `python -m parser.extraccion.test_geometria`.

Cubre `contrastar_filas` (agreement sube confianza, corrimiento de fila
genera discrepancia), el fail-closed de `AdaptadorGeometriaVendor` sin
credenciales de AWS resolubles, el gate de `vendor_produccion_ok`, y la
traducción de la respuesta real de Textract (`Blocks`/`CELL`) a
`FilaGeometrica` — todo sin llamar a ningún vendor real ni requerir red.
"""

import tempfile

from parser.cobertura_calidad.coverage import VariableValue
from parser.extraccion.geometria import contrastar_filas
from parser.vocabulario import puerto_geometria
from parser.vocabulario.puerto_geometria import AdaptadorGeometriaVendor, FilaGeometrica


class _PuertoGeometriaFalso:
    """Fake de PuertoGeometria: .ordenar_filas(path) devuelve directamente
    la lista de FilaGeometrica preseteada, sin llamar a ningún vendor real
    — mismo espíritu que _PuertoLLMFalso en test_estrategias.py."""

    def __init__(self, filas: list[FilaGeometrica]):
        self._filas = filas
        self.ultimo_path = None

    def ordenar_filas(self, path: str) -> list[FilaGeometrica]:
        self.ultimo_path = path
        return self._filas


def _variable_con_etiqueta(valor, confianza, etiqueta_fila):
    vv = VariableValue(valor, "migracion_foto", confianza)
    vv.etiqueta_fila = etiqueta_fila  # Fase 2 agrega este campo de forma real
    return vv


def test_puerto_geometria_falso_registra_el_path_y_no_llama_red():
    filas = [FilaGeometrica(etiqueta="No-shows", y_top=0.1, orden=0)]
    puerto = _PuertoGeometriaFalso(filas)
    resultado = puerto.ordenar_filas("/tmp/foto.jpg")
    assert resultado == filas
    assert puerto.ultimo_path == "/tmp/foto.jpg"


def test_contrastar_filas_coincide_sube_confianza():
    variables = {
        "no_shows": _variable_con_etiqueta(16, 0.5, "No-shows"),
    }
    filas_geometricas = [FilaGeometrica(etiqueta="No-shows", y_top=0.1, orden=0)]
    confianza_actualizada, discrepancias = contrastar_filas(variables, filas_geometricas)
    assert confianza_actualizada["no_shows"] == 0.7
    assert discrepancias == {}


def test_contrastar_filas_corrimiento_de_fila_no_sube_confianza_y_genera_discrepancia():
    # "no_shows" es la primera variable con etiqueta_fila (orden original 0),
    # pero la geometría la detecta en la fila 2 — un corrimiento de 2,
    # mayor que la tolerancia default (1).
    variables = {
        "no_shows": _variable_con_etiqueta(16, 0.5, "No-shows"),
    }
    filas_geometricas = [
        FilaGeometrica(etiqueta="Turnos agendados", y_top=0.05, orden=0),
        FilaGeometrica(etiqueta="Cancelaciones", y_top=0.15, orden=1),
        FilaGeometrica(etiqueta="No-shows", y_top=0.25, orden=2),
    ]
    confianza_actualizada, discrepancias = contrastar_filas(variables, filas_geometricas)
    assert confianza_actualizada == {}
    assert discrepancias["no_shows"] == {
        "etiqueta": "No-shows",
        "original_orden": 0,
        "orden_geometria": 2,
    }


def test_contrastar_filas_devuelve_mismo_shape_de_tupla_que_contrastar():
    confianza_actualizada, discrepancias = contrastar_filas({}, [])
    assert isinstance(confianza_actualizada, dict)
    assert isinstance(discrepancias, dict)


def test_contrastar_filas_variable_sin_etiqueta_fila_se_salta_en_silencio():
    # Hoy (antes de la Fase 2) ninguna VariableValue real tiene
    # etiqueta_fila — contrastar_filas no debe romper, solo no contrastar
    # nada para esa variable.
    variables = {"no_shows": VariableValue(16, "migracion_foto", 0.5)}
    filas_geometricas = [FilaGeometrica(etiqueta="No-shows", y_top=0.1, orden=0)]
    confianza_actualizada, discrepancias = contrastar_filas(variables, filas_geometricas)
    assert confianza_actualizada == {}
    assert discrepancias == {}


class _SesionAwsFalsaSinCredenciales:
    """Fake de boto3.Session: simula una máquina sin AWS_ACCESS_KEY_ID/
    AWS_SECRET_ACCESS_KEY ni ~/.aws/credentials, sin tocar el entorno
    real (que en esta máquina sí tiene credenciales de `aws configure`)."""

    def __init__(self, region_name=None):
        pass

    def get_credentials(self):
        return None


def test_adaptador_geometria_vendor_sin_credenciales_aws_falla_cerrado():
    sesion_original = puerto_geometria.boto3.Session
    puerto_geometria.boto3.Session = _SesionAwsFalsaSinCredenciales
    try:
        fallo = False
        try:
            AdaptadorGeometriaVendor()
        except RuntimeError as error:
            fallo = True
            assert "credenciales" in str(error).lower()
        assert fallo, "sin credenciales de AWS tiene que fallar cerrado, no intentar mandar nada"
    finally:
        puerto_geometria.boto3.Session = sesion_original


def test_adaptador_geometria_vendor_produccion_no_ok_no_llama_al_vendor():
    class _ClienteTextractQueNuncaDeberiaLlamarse:
        def analyze_document(self, **kwargs):
            raise AssertionError("no debería llamarse con vendor_produccion_ok=False")

    adaptador = AdaptadorGeometriaVendor(
        vendor_produccion_ok=False,
        cliente_textract=_ClienteTextractQueNuncaDeberiaLlamarse(),
    )
    fallo = False
    try:
        adaptador.ordenar_filas("/tmp/no-importa-no-se-llega-a-abrir.png")
    except AssertionError as error:
        fallo = True
        assert "vendor_produccion_ok" in str(error)
    assert fallo, "vendor_produccion_ok=False tiene que frenar antes de tocar red o disco"


def _bloque_celda(id_bloque, row_index, column_index, ids_hijos):
    return {
        "BlockType": "CELL",
        "Id": id_bloque,
        "RowIndex": row_index,
        "ColumnIndex": column_index,
        "Geometry": {"BoundingBox": {"Top": 0.1 * row_index}},
        "Relationships": [{"Type": "CHILD", "Ids": ids_hijos}],
    }


def _bloque_word(id_bloque, texto):
    return {"BlockType": "WORD", "Id": id_bloque, "Text": texto}


def test_filas_desde_respuesta_ignora_columna_de_valores_y_pasa_a_0_based():
    # Mismo shape real que devuelve AnalyzeDocument: RowIndex 1-based,
    # dos columnas (Concepto/Valor). Solo ColumnIndex==1 (las etiquetas)
    # tiene que sobrevivir a la traducción.
    respuesta = {
        "Blocks": [
            _bloque_celda("celda-header-concepto", row_index=1, column_index=1, ids_hijos=["w1"]),
            _bloque_word("w1", "Concepto"),
            _bloque_celda("celda-header-valor", row_index=1, column_index=2, ids_hijos=["w2"]),
            _bloque_word("w2", "Valor"),
            _bloque_celda("celda-etiqueta", row_index=2, column_index=1, ids_hijos=["w3", "w4"]),
            _bloque_word("w3", "No-shows"),
            _bloque_word("w4", "hoy"),
            _bloque_celda("celda-valor", row_index=2, column_index=2, ids_hijos=["w5"]),
            _bloque_word("w5", "16"),
        ]
    }

    filas = AdaptadorGeometriaVendor._filas_desde_respuesta(respuesta)

    assert [(f.etiqueta, f.orden) for f in filas] == [("Concepto", 0), ("No-shows hoy", 1)]
    assert all(f.etiqueta not in ("Valor", "16") for f in filas)


def test_ordenar_filas_llama_al_cliente_inyectado_y_devuelve_filas_traducidas():
    respuesta_falsa = {
        "Blocks": [
            _bloque_celda("celda-1", row_index=1, column_index=1, ids_hijos=["w1"]),
            _bloque_word("w1", "No-shows"),
        ]
    }

    class _ClienteTextractFalso:
        def __init__(self):
            self.ultima_llamada = None

        def analyze_document(self, **kwargs):
            self.ultima_llamada = kwargs
            return respuesta_falsa

    cliente = _ClienteTextractFalso()
    adaptador = AdaptadorGeometriaVendor(vendor_produccion_ok=True, cliente_textract=cliente)

    with tempfile.NamedTemporaryFile(suffix=".png") as archivo_temporal:
        archivo_temporal.write(b"contenido-de-prueba-no-es-una-imagen-real")
        archivo_temporal.flush()
        filas = adaptador.ordenar_filas(archivo_temporal.name)

    assert filas == [FilaGeometrica(etiqueta="No-shows", y_top=0.1, orden=0)]
    assert cliente.ultima_llamada["FeatureTypes"] == ["TABLES"]
    assert cliente.ultima_llamada["Document"]["Bytes"] == b"contenido-de-prueba-no-es-una-imagen-real"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
