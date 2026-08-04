"""
estacionalidad.py

Fase 4 del plan de evolución: la estacionalidad de Mar del Plata como dato
estructurado, en vez de depender por completo de que Claude recuerde
aplicar la regla 5 de `interpretacion.SYSTEM_PROMPT_BASE` a partir de una
respuesta de texto libre (P51 de la Guía de Diagnóstico). Esto le da a
`diagnostico.py` una señal determinista para cruzar contra KPI 4 (no-show)
y KPI 12 (producción por hora-sillón) durante los meses de temporada.

Limitación honesta: P51 sigue siendo texto libre ("en enero-febrero se
complica más"), no hay forma determinista de parsear "qué mes exacto"
dice el dueño sin NLP. Mientras tanto, se usa la estacionalidad turística
conocida de Mar del Plata (verano) como proxy razonable — funciona para
la mayoría real de las clínicas de la zona, pero es un proxy, no un
parseo de la respuesta real.
"""

from typing import Optional

MESES_TEMPORADA_ALTA = {"01", "02", "12"}  # verano: pico turístico en Mar del Plata


def declara_estacionalidad(respuestas: dict[str, str]) -> bool:
    return bool(respuestas.get("P51", "").strip())


def mes_en_temporada_declarada(periodo: str, respuestas: dict[str, str]) -> Optional[bool]:
    """True/False si `periodo` ("2026-01") cae en la época que el dueño
    declaró como complicada en P51. None si P51 no está respondida — no
    hay con qué comparar, y no se asume nada en su ausencia."""
    if not declara_estacionalidad(respuestas):
        return None
    partes = periodo.split("-")
    if len(partes) < 2:
        return None
    return partes[1] in MESES_TEMPORADA_ALTA
