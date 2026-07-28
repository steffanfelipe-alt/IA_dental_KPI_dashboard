"""
evals/casos_diagnostico.py

Fase 8 del plan de evolución. El §24 del Documento Maestro pide validar
el Diagnostic Engine contra casos reales anonimizados con diagnóstico de
un experto humano, ANTES de confiar en él en producción. Esta sesión no
tiene casos reales de clínicas ni un experto disponible para etiquetarlos
— eso es un proceso, no algo que se pueda simular con código.

Lo que este archivo SÍ hace: casos sintéticos (mismo patrón que
evals/casos_dorados.py usa para el parser) que fijan el comportamiento
esperado del motor determinista (diagnostico.py + catalogo_tecnologico.py
+ priorizacion.py) para no perder cobertura de regresión mientras se
consigue el dataset real. Son un piso, no un reemplazo del §24.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CasoDiagnostico:
    nombre: str
    descripcion: str
    kpis_calculados: dict
    respuestas_diagnostico: dict
    # Expectativas — todas opcionales, se chequea solo lo que el caso declara
    cuello_de_botella_esperado: Optional[int] = None  # kpi_id que debería ganar la priorización
    debe_tener_contradiccion: bool = False
    debe_tener_patron_cruzado: bool = False
    estado_esperado: Optional[str] = None  # nombre de EstadoEvidencia para cuello_de_botella_esperado
    debe_generar_oportunidades: bool = True


CASOS: list[CasoDiagnostico] = [
    CasoDiagnostico(
        "no_show_critico_con_contradiccion",
        "No-show muy por encima del benchmark (confiabilidad consultora_ar) y la "
        "clínica ya declara confirmación automática — el motor no debería "
        "limitarse a repetir 'agregar recordatorios'.",
        kpis_calculados={4: {"valor": 40.0, "serie": None}},
        respuestas_diagnostico={"P2": "Mandamos un recordatorio automático 48hs y 24hs antes"},
        cuello_de_botella_esperado=4,
        debe_tener_contradiccion=True,
        estado_esperado="CRITICAL",
    ),
    CasoDiagnostico(
        "mix_de_tratamientos_no_cierre",
        "Aceptación de presupuestos alta y ticket promedio bajo al mismo tiempo — "
        "el motor debería reconocer el patrón de mix, no tratarlos como dos "
        "problemas sueltos.",
        kpis_calculados={5: {"valor": 80.0, "serie": None}, 6: {"valor": 20000.0, "serie": None}},
        respuestas_diagnostico={},
        debe_tener_patron_cruzado=True,
    ),
    CasoDiagnostico(
        "agendamiento_sin_compromiso",
        "Tasa de agendamiento alta con no-show también alto — patrón de gente "
        "agendada sin compromiso real.",
        kpis_calculados={3: {"valor": 90.0, "serie": None}, 4: {"valor": 30.0, "serie": None}},
        respuestas_diagnostico={},
        debe_tener_patron_cruzado=True,
    ),
    CasoDiagnostico(
        "clinica_sana",
        "Todos los KPIs dentro de rango — el motor NO debería inventar un "
        "problema donde no lo hay (falso diagnóstico).",
        kpis_calculados={4: {"valor": 12.0, "serie": None}, 5: {"valor": 70.0, "serie": None}},
        respuestas_diagnostico={},
        debe_generar_oportunidades=False,
    ),
    CasoDiagnostico(
        "evidencia_insuficiente",
        "KPI sin benchmark (7) y sin serie histórica — el motor debería admitir "
        "que no alcanza evidencia, no inventar una causa.",
        kpis_calculados={7: {"valor": 55.0, "serie": None}},
        respuestas_diagnostico={},
        cuello_de_botella_esperado=7,
        estado_esperado="INSUFFICIENT_EVIDENCE",
        debe_generar_oportunidades=False,
    ),
]
