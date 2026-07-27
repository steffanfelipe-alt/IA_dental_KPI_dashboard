# Agencia IA — Dashboard de KPIs para Clínicas Dentales

Contenido de esta entrega:

- **Preguntas_Diagnostico_Odontologia_v2.docx** — Guía de Diagnóstico Integral
  (53 preguntas originales + P9b y P21b agregadas para cubrir consultas
  nuevas/mes y ticket promedio, más la nota sobre por qué 7 KPIs financieros
  no se preguntan verbalmente).

- **parser/** — Motor de KPIs: esquema de variables + las 20 fórmulas
  (`schema.py`), chequeo de cobertura por variable (`coverage.py`),
  resolución de conflictos de migración (`conflictos.py`), preguntas
  reales del wizard (`preguntas_wizard.py`), orquestador (`pipeline.py`),
  los dos extractores (`extractors/`), la estructura de benchmarks
  argentinos ya cargada (`benchmarks.py` + `aranceles_com.py`), el cruce
  de benchmark + contexto cualitativo (`interpretacion.py`) y el motor de
  priorización (`priorizacion.py`). Ver `parser/README.md` para el detalle
  de uso y las decisiones de diseño.

- **parser/referencias/benchmarks_research_AR.md** — el research completo
  de benchmarks argentinos (13 indicadores) del que salieron los valores
  cargados en `benchmarks.py`.

- **plan_maestro_benchmarks_interpretacion.md** — plan de integración de
  benchmarks + interpretación IA al sistema. Ejecutado (ver estado abajo).

- **plan_resolucion_conflictos.md** — plan para cuando dos archivos
  migrados dan valores distintos para la misma variable con confianza
  empatada. Independiente del plan de benchmarks. Ejecutado.

## Referencia externa

El mapa completo de arquitectura (stack, interfaces, flujo del onboarding,
sistema de priorización) vive en el tablero de Miro, no en este zip:
https://miro.com/app/board/uXjVH3if4pU=/ — **todavía no actualizado** con
la Sección 7 (capa de interpretación y benchmarks) que documenta este flujo.

## Estado real al momento de esta entrega (auditado, no asumido)

- `benchmarks.py` tiene los 13 valores cargados desde el research, con
  `mejor_es` y `es_multiplo_arancel` resueltos. 3 KPIs (7, 10, 19) quedan
  `sin_benchmark` a propósito — no hay proxy confiable. Ver el detalle en
  `parser/README.md`.
- `interpretacion.py` tiene las reglas nuevas del plan maestro (sesgo
  comercial de fuentes, eje temporal benchmark-vs-historial vía
  `peso_benchmark_vs_historial`, P51/estacionalidad conectado a KPIs 4 y
  12) — probado con payloads sintéticos (`client=None`), no contra la API
  real de Anthropic todavía.
- `priorizacion.py` es nuevo: implementa el motor de priorización
  (score = gap × impacto × factor_confiabilidad) que antes solo estaba
  diagramado en el Miro.
- Los extractores (`excel_parser.py`, `vision_parser.py`) están escritos
  pero nunca se probaron contra un archivo real ni con API key conectada.
- No hay wizard de frontend, ni endpoint de FastAPI real (solo
  documentado como ejemplo en `parser/README.md`), ni conexión a
  Supabase, ni workflows de n8n — todo eso sigue siendo diseño, no código.
- Este zip no se reempaquetó todavía con los cambios de esta entrega
  (`~/Downloads/agencia_ia_dental_dashboard.zip` es una versión anterior).
