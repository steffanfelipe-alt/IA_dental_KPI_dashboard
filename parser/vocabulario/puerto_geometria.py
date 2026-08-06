"""
puerto_geometria.py

Puerto (Protocol/Adapter, mismo espíritu que puerto_llm.py) para una
verificación de geometría independiente del camino semántico de
extracción: un vendor de Document AI (OCR + layout) que devuelve, para
una foto, el orden real de sus filas de arriba a abajo — dato que Claude
también reporta por su cuenta (`etiqueta_fila` en cada variable extraída,
ver vision_parser.py) pero sin ninguna garantía geométrica: Claude puede
leer bien los NÚMEROS y confundir a qué FILA pertenecen.

Este puerto es deliberadamente independiente de PuertoLLM (no hereda ni
comparte tipos con él): no es una segunda opinión semántica como
segunda_lectura.py, es una segunda fuente de DATOS DE LAYOUT — otra
tecnología (OCR/geometría, no un LLM) mirando el mismo archivo desde otro
ángulo. Los callers de este puerto (parser/extraccion/geometria.py y
pipeline.py) no conocen ningún SDK de vendor — solo hablan contra
`PuertoGeometria`.

Vendor elegido: AWS Textract (Fase 5)
--------------------------------------
La elección original (Azure Document Intelligence, por retención de
datos y free tier permanente) quedó bloqueada por un problema de medio
de pago ajeno a lo técnico: Azure rechaza tarjetas prepagas y la única
tarjeta disponible es de Mercado Pago. AWS sí aceptó el alta. Validado
2026-08-05 contra dos fotos reales de prueba (incluida la foto exacta
que originó el Bug #1a en `INFORME_BUGS_END_TO_END.md`): `AnalyzeDocument`
con `FeatureTypes=["TABLES"]` agrupó 20/20 filas correctamente, incluso
sin bordes de tabla visibles en la imagen.

Autenticación: a diferencia de PuertoLLM/Anthropic, AWS no tiene una
sola "API key" — son un par de credenciales (Access Key ID + Secret
Access Key) más región. Este adapter no inventa su propia variable de
entorno: delega la resolución completa a la cadena estándar de boto3
(`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/región, o lo que haya
guardado `aws configure` en `~/.aws/credentials`) y falla cerrado si no
encuentra nada resoluble, mismo espíritu que el chequeo de
`GEOMETRIA_API_KEY` de la versión anterior de este módulo.

Reintentos: en vez de escribir un loop de retry a mano, se configura el
retry "standard" incorporado de botocore (`Config(retries=...)`) — ya
resuelve backoff exponencial ante throttling/errores transitorios de
Textract, probado por AWS. Reinventar esa lógica acá sería duplicar algo
que el SDK ya cubre.

`vendor_produccion_ok` (default False) sigue siendo el gate explícito de
producción: además de credenciales válidas, requiere que la pantalla de
consentimiento del paciente ya esté en el UI de onboarding (gate legal
bajo Ley 25.326 — ver Requirement "DPA/BAA Gate Before Real Patient
Photos" del spec) antes de mandar una foto real. Ninguna credencial ni
config de AWS reemplaza ese consentimiento.
"""

from dataclasses import dataclass
from typing import Any, Optional, Protocol

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import NoRegionError
except ImportError:  # pragma: no cover
    boto3 = None
    Config = None
    NoRegionError = Exception


REINTENTOS_DEFAULT = 3


@dataclass
class FilaGeometrica:
    """Una fila detectada por el vendor de geometría, ya ordenada de
    arriba a abajo. `etiqueta` es el texto OCR'd de la fila (se
    contrasta contra `VariableValue.etiqueta_fila` en geometria.py);
    `y_top` es la posición vertical normalizada que el vendor usó para
    ordenar; `orden` es el índice 0-based resultante de esa ordenación
    (lo único que geometria.contrastar_filas realmente necesita)."""

    etiqueta: str
    y_top: float
    orden: int


class PuertoGeometria(Protocol):
    """Lo único que la verificación de geometría necesita de un vendor:
    mandarle una foto y recibir sus filas ya ordenadas de arriba a abajo.
    Vendor-agnóstico a propósito — ningún caller de este puerto importa
    un SDK de vendor directamente (Requirement "PuertoGeometria Port
    Contract")."""

    def ordenar_filas(self, path: str) -> list[FilaGeometrica]:
        ...


class AdaptadorGeometriaVendor:
    """Único lugar del código que conoce AWS Textract. Traduce la
    respuesta de `AnalyzeDocument` (grafo de `Blocks`/`CELL`, `RowIndex`
    1-based) a `FilaGeometrica` (0-based) — ningún vocabulario de
    Textract cruza este límite hacia geometria.py/pipeline.py."""

    def __init__(
        self,
        vendor_produccion_ok: bool = False,
        region_name: Optional[str] = None,
        cliente_textract: Optional[Any] = None,
        reintentos: int = REINTENTOS_DEFAULT,
    ):
        self._vendor_produccion_ok = vendor_produccion_ok

        if cliente_textract is not None:
            self._cliente = cliente_textract
            return

        assert boto3 is not None, "Instalar el SDK: pip install boto3"
        sesion = boto3.Session(region_name=region_name)
        if sesion.get_credentials() is None:
            raise RuntimeError(
                "Sin credenciales de AWS resolubles (AWS_ACCESS_KEY_ID/"
                "AWS_SECRET_ACCESS_KEY, o ~/.aws/credentials vía `aws "
                "configure`): sin credencial no se manda ninguna foto al "
                "vendor de geometría (falla cerrado — Requirement 'Vendor "
                "Credential via Environment Variable')."
            )
        try:
            self._cliente = sesion.client(
                "textract",
                config=Config(retries={"max_attempts": reintentos, "mode": "standard"}),
            )
        except NoRegionError as error:
            raise RuntimeError(
                "Sin región de AWS resoluble: pasar region_name explícito, "
                "setear AWS_REGION/AWS_DEFAULT_REGION, o correr `aws "
                "configure`."
            ) from error

    def ordenar_filas(self, path: str) -> list[FilaGeometrica]:
        assert self._vendor_produccion_ok, (
            "AdaptadorGeometriaVendor.ordenar_filas: vendor_produccion_ok=False "
            "— falta confirmar el consentimiento del paciente en el UI de "
            "onboarding antes de mandar una foto real (Fase 5, gate legal "
            "bajo Ley 25.326). Usar _PuertoGeometriaFalso en tests."
        )
        with open(path, "rb") as archivo:
            bytes_documento = archivo.read()

        respuesta = self._cliente.analyze_document(
            Document={"Bytes": bytes_documento},
            FeatureTypes=["TABLES"],
        )
        return self._filas_desde_respuesta(respuesta)

    @staticmethod
    def _filas_desde_respuesta(respuesta: dict) -> list[FilaGeometrica]:
        """Solo la primera columna de cada tabla (las etiquetas de fila)
        se traduce a FilaGeometrica — la segunda columna (el valor) no le
        interesa a este puerto, eso lo sigue leyendo Claude. `RowIndex`
        de Textract es 1-based; `FilaGeometrica.orden` es 0-based (ver
        docstring de la clase) — acá es donde se hace esa resta, para
        que ningún caller de este puerto tenga que saber que Textract
        cuenta desde 1."""
        bloques = respuesta.get("Blocks", [])
        por_id = {bloque["Id"]: bloque for bloque in bloques}

        def texto_de_celda(celda: dict) -> str:
            palabras = []
            for relacion in celda.get("Relationships", []):
                if relacion["Type"] != "CHILD":
                    continue
                for id_hijo in relacion["Ids"]:
                    hijo = por_id.get(id_hijo)
                    if hijo is not None and hijo["BlockType"] == "WORD":
                        palabras.append(hijo["Text"])
            return " ".join(palabras)

        filas = []
        for bloque in bloques:
            if bloque["BlockType"] != "CELL" or bloque.get("ColumnIndex") != 1:
                continue
            etiqueta = texto_de_celda(bloque)
            if not etiqueta:
                continue
            filas.append(
                FilaGeometrica(
                    etiqueta=etiqueta,
                    y_top=bloque["Geometry"]["BoundingBox"]["Top"],
                    orden=bloque["RowIndex"] - 1,
                )
            )
        return filas
