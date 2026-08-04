"""
estrategias.py

Strategy Pattern para la extracción: cada tipo de archivo (Excel/CSV,
imagen, PDF) es una estrategia intercambiable con el mismo contrato
(`EstrategiaExtraccion.extraer`) y la misma forma de retorno
(`ResultadoExtraccion`) — reemplaza dos hacks que tenía `pipeline.py`:

  - `isinstance(resultado, tuple)`: excel_parser devolvía
    (variables, tasas_declaradas) y vision_parser sólo variables;
    pipeline.py tenía que adivinar la forma del resultado según qué
    extractor se hubiera usado. Ahora las tres estrategias siempre
    devuelven `ResultadoExtraccion`, con `tasas_declaradas={}` por
    default para las que no las conocen (vision).

  - `inspect.signature(extractor).parameters` para decidir si pasar
    `registro_clientes`: ahora es un parámetro explícito del contrato
    `EstrategiaExtraccion.extraer` — todas lo aceptan, las que no lo
    necesitan (imagen, PDF) simplemente lo ignoran. No cambia el
    comportamiento de hoy: esas dos nunca lo usaban, ahora sólo lo
    reciben sin usarlo.
"""

from dataclasses import dataclass, field
from typing import Optional, Protocol

from parser.cobertura_calidad.coverage import VariableValue
from parser.extraccion import excel_parser, vision_parser
from parser.pacientes.matching import RegistroClientes
from parser.vocabulario.puerto_llm import PuertoLLM


@dataclass
class ResultadoExtraccion:
    """Forma única que devuelve toda `EstrategiaExtraccion`."""

    variables: dict[str, VariableValue]
    tasas_declaradas: dict[int, object] = field(default_factory=dict)


class EstrategiaExtraccion(Protocol):
    def extraer(
        self,
        path: str,
        puerto_llm: PuertoLLM,
        *,
        registro_clientes: Optional[RegistroClientes] = None,
    ) -> ResultadoExtraccion:
        ...


class ExtraccionExcel:
    """Excel/CSV — envuelve `excel_parser.parsear_excel`, el único de los
    tres que hoy usa `registro_clientes` de verdad (Fase 2 de
    matching.py: fusiona variantes del mismo paciente entre archivos)."""

    def extraer(
        self,
        path: str,
        puerto_llm: PuertoLLM,
        *,
        registro_clientes: Optional[RegistroClientes] = None,
    ) -> ResultadoExtraccion:
        variables, tasas_declaradas = excel_parser.parsear_excel(
            path, puerto_llm, registro_clientes=registro_clientes,
        )
        return ResultadoExtraccion(variables=variables, tasas_declaradas=tasas_declaradas)


class ExtraccionVisionImagen:
    """Foto/captura de pantalla — envuelve `vision_parser.parsear_imagen`.
    No tiene ninguna noción de tasas declaradas ni de registro_clientes
    (una foto no arma ledger por paciente hoy) — acepta el parámetro por
    contrato y lo ignora, sin cambiar el comportamiento de siempre."""

    def extraer(
        self,
        path: str,
        puerto_llm: PuertoLLM,
        *,
        registro_clientes: Optional[RegistroClientes] = None,
    ) -> ResultadoExtraccion:
        variables = vision_parser.parsear_imagen(path, puerto_llm)
        return ResultadoExtraccion(variables=variables)


class ExtraccionVisionPDF:
    """PDF — envuelve `vision_parser.parsear_pdf`. Mismo criterio que
    `ExtraccionVisionImagen` respecto a `registro_clientes`."""

    def extraer(
        self,
        path: str,
        puerto_llm: PuertoLLM,
        *,
        registro_clientes: Optional[RegistroClientes] = None,
    ) -> ResultadoExtraccion:
        variables = vision_parser.parsear_pdf(path, puerto_llm)
        return ResultadoExtraccion(variables=variables)
