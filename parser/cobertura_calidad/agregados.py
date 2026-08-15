"""
agregados.py

Punto 1 del doc de deficiencias-parser-kpis.md: en vez de pedirle al LLM
que resuma ("dame el promedio de la serie"), tarea donde falla justo en
los extremos de una tabla larga, se le pide que extraiga filas atómicas
—`VariableValue.serie` ya hace exactamente eso— y el agregado se calcula
acá, en Python determinístico. Cero alucinación posible en esta parte:
sumar y promediar no es algo en lo que un LLM pueda "equivocarse un poco".

`calcular_agregado` nunca reemplaza a `VariableValue.valor` (que sigue
siendo el último período real — ver decisión 2 del plan, y el hallazgo
1.1 que ese diseño ya cerró: una fila TOTAL/Promedio no debe colarse como
si fuera un período más). Los agregados van al lado, en un campo separado.
"""

from typing import Optional


def _mediana(valores: list[float]) -> Optional[float]:
    if not valores:
        return None
    ordenados = sorted(valores)
    n = len(ordenados)
    medio = n // 2
    if n % 2 == 0:
        return (ordenados[medio - 1] + ordenados[medio]) / 2
    return float(ordenados[medio])


def _valores_numericos(serie: dict) -> list[float]:
    return [v for v in serie.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]


def calcular_agregado(serie: dict, metodo: str = "promedio") -> Optional[float]:
    """`metodo`: "promedio" | "mediana" | "suma" | "ultimo".
    Ignora entradas no numéricas de la serie (ej. el KPI 19, cuyo
    valor por período es un dict) en vez de romper — si no queda ningún
    valor numérico, devuelve None."""
    valores = _valores_numericos(serie)
    if not valores:
        return None

    if metodo == "promedio":
        return round(sum(valores) / len(valores), 4)
    if metodo == "mediana":
        return round(_mediana(valores), 4)
    if metodo == "suma":
        return round(sum(valores), 4)
    if metodo == "ultimo":
        # Usa `valores` (ya filtrado), NO serie.values() crudo: un KPI
        # porcentual (_pct en schema.py) devuelve None para un período
        # cuyo denominador dio 0 — ej. un mes sin turnos agendados. Si ese
        # período resulta ser el más reciente, tomar serie.values()[-1] a
        # ciegas explota con TypeError en vez de saltear al último valor
        # realmente numérico (bug real, encontrado probando con datos
        # reales — no una hipótesis). Confía en el orden de inserción del
        # dict, igual que VariableValue.valor — el llamador es responsable
        # de pasar una serie ya ordenada cronológicamente (ver
        # periodos.orden_cronologico).
        return round(float(valores[-1]), 4)
    raise ValueError(f"método de agregación desconocido: {metodo!r}")


def detectar_outliers(serie: dict, factor: float = 10) -> list[str]:
    """Períodos cuyo valor se aleja >= `factor` veces de la mediana del
    resto de la serie. No descarta nada — es la misma filosofía que
    `variables_en_cuarentena`: lo dudoso queda visible y trazable, nunca
    desaparece en silencio ni altera el agregado."""
    numericos = {p: v for p, v in serie.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    if len(numericos) < 2:
        return []

    sospechosos = []
    for periodo, valor in numericos.items():
        resto = [v for p, v in numericos.items() if p != periodo]
        mediana_resto = _mediana(resto)
        if not mediana_resto:
            continue  # mediana 0: no hay forma multiplicativa de juzgar el resto
        if valor >= mediana_resto * factor or valor <= mediana_resto / factor:
            sospechosos.append(periodo)
    return sospechosos
