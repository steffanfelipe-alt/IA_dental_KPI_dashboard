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
ángulo. Los callers de este puerto (parser/extraccion/geometria.py y,
más adelante, pipeline.py) no conocen ningún SDK de vendor — solo hablan
contra `PuertoGeometria`.

Por qué el adapter real todavía es un stub
-------------------------------------------
La elección de vendor (AWS Textract / Google Document AI / Azure Document
Intelligence), el costo por página, y sobre todo un DPA/BAA firmado +
consentimiento del paciente para mandarle una foto real a un tercero,
son decisiones de Felipe, no técnicas — están bloqueadas (ver Fase 5 de
tasks.md y el Requirement "DPA/BAA Gate Before Real Patient Photos" del
spec). Hasta que eso se resuelva, `AdaptadorGeometriaVendor.ordenar_filas`
no manda nada: el flag `vendor_produccion_ok` (default False) tiene que
pasarse en True explícitamente, y aun así hoy tira `NotImplementedError`
porque no hay vendor elegido todavía. Los tests y cualquier pipeline que
quiera ejercitar el contraste sin un vendor real usan
`_PuertoGeometriaFalso` (ver test_geometria.py).
"""

import os
from dataclasses import dataclass
from typing import Protocol


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
    """Stub del adapter real (Fase 5, bloqueado — ver docstring del
    módulo). Ya implementa el gate de credencial y de "producción OK" que
    exige el spec, para que quien construya este objeto hoy (nadie en
    producción todavía: `procesar_migracion` recibe `puerto_geometria=None`
    por default) no pueda accidentalmente mandar una foto real antes de
    tiempo."""

    def __init__(self, vendor_produccion_ok: bool = False):
        api_key = os.environ.get("GEOMETRIA_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta GEOMETRIA_API_KEY en el entorno: sin credencial no se manda "
                "ninguna foto al vendor de geometría (falla cerrado — Requirement "
                "'Vendor Credential via Environment Variable')."
            )
        self._api_key = api_key
        self._vendor_produccion_ok = vendor_produccion_ok

    def ordenar_filas(self, path: str) -> list[FilaGeometrica]:
        assert self._vendor_produccion_ok, (
            "AdaptadorGeometriaVendor.ordenar_filas: vendor_produccion_ok=False — "
            "el vendor real todavía no está elegido (Fase 5, bloqueado por DPA/BAA "
            "y la elección de vendor de Felipe). No se manda ninguna foto real "
            "hasta entonces; usar _PuertoGeometriaFalso en tests."
        )
        raise NotImplementedError(
            "Llamada real al vendor de geometría: pendiente de elección de vendor "
            "(AWS Textract / Google Document AI / Azure Document Intelligence), "
            "costo por página y DPA/BAA firmado — ver Fase 5 de tasks.md."
        )
