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
  de benchmark + contexto cualitativo (`interpretacion.py`), el motor de
  priorización (`priorizacion.py`), el Diagnostic Engine
  (`diagnostico.py`), el catálogo de ~45 intervenciones tecnológicas
  (`catalogo_tecnologico.py`) y el ledger de pacientes
  (`ledger.py` + `metricas_paciente.py`), entre ~20 módulos más. Ver
  `parser/README.md` para la lista completa (agrupada por función) y las
  decisiones de diseño.

- **parser/referencias/benchmarks_research_AR.md** — el research completo
  de benchmarks argentinos (13 indicadores) del que salieron los valores
  cargados en `benchmarks.py`.

- **plan_maestro_benchmarks_interpretacion.md** — plan de integración de
  benchmarks + interpretación IA al sistema. Ejecutado (ver estado abajo).

- **plan_resolucion_conflictos.md** — plan para cuando dos archivos
  migrados dan valores distintos para la misma variable con confianza
  empatada. Independiente del plan de benchmarks. Ejecutado.

- **CONTRIBUTING.md** — guía de contribución y desarrollo seguro: testing
  con IA de por medio, CI/CD, flujo de Pull Requests (reglas de oro),
  GitHub Actions del repo, protección de `main`, review de seguridad con IA
  (paso futuro) y release-please. Incluye el checklist antes de abrir un PR.
  Leerla antes de sumar cambios.

## Referencia externa

El mapa completo de arquitectura (stack, interfaces, flujo del onboarding,
sistema de priorización) vive en el tablero de Miro, no en este zip:
https://miro.com/app/board/uXjVH3if4pU=/ — **todavía no actualizado** con
la Sección 7 (capa de interpretación y benchmarks) que documenta este flujo.

## Estado real (auditado, no asumido) — actualizado 2026-07-30

- `benchmarks.py` tiene los 13 valores cargados desde el research, con
  `mejor_es` y `es_multiplo_arancel` resueltos. 3 KPIs (7, 10, 19) quedan
  `sin_benchmark` a propósito — no hay proxy confiable. Ver el detalle en
  `parser/README.md`.
- `interpretacion.py` tiene las reglas del plan maestro (sesgo comercial
  de fuentes, eje temporal benchmark-vs-historial vía
  `peso_benchmark_vs_historial`, P51/estacionalidad conectado a KPIs 4 y
  12), más un tercer entry point (`interpretar_clinica`, el informe de 10
  secciones). **Los tres corrieron contra la API real de Anthropic**, no
  sólo con payloads sintéticos — con archivos de una clínica real.
- `priorizacion.py` implementa el motor de priorización
  (score = gap × impacto × addressability × suficiencia) que antes solo
  estaba diagramado en el Miro.
- **Los extractores se probaron extensamente contra archivos reales de
  una clínica** (Excel de 3 hojas, 2 CSV transaccionales, 1 foto
  manuscrita), no sólo escritos: `excel_parser.py` extrae y mapea
  columnas ambiguas, incluido un ledger de historial por paciente que
  desbloquea el KPI de valor del paciente (LTV); `vision_parser.py` leyó
  la foto real y mapeó los datos correctos.
- Desde esta entrega se agregaron, y están commiteados y probados:
  motor de cruces determinísticos y propuestos por IA (`cruces.py` +
  `cruces_propuestos.py`), Diagnostic Engine (`diagnostico.py`), catálogo
  de ~45 intervenciones tecnológicas priorizadas (`catalogo_tecnologico.py`),
  ledger de pacientes con 17 métricas longitudinales
  (`ledger.py` + `metricas_paciente.py`), y una capa que traduce los
  motivos técnicos de rechazo de datos a lenguaje de dueño de clínica
  (`explicaciones.py`). Detalle completo, fase por fase, en
  `parser/README.md`.
- **Sigue sin existir**: wizard de frontend, endpoint de FastAPI real
  (sólo documentado como ejemplo en `parser/README.md`), conexión a
  Supabase, workflows de n8n. La diferencia respecto de la entrega
  anterior es que la **lógica que esos tres necesitarían ya está
  terminada y probada** (`pipeline.procesar_migracion` y
  `resolver_conflicto` son funciones puras — reciben paths y dicts,
  devuelven un payload JSON-serializable, sin ningún import de
  Streamlit) — falta la envoltura de producto, no el motor.
- Pendiente sin verificar en esta entrega: si el tablero de Miro
  (`https://miro.com/app/board/uXjVH3if4pU=/`) y el zip de
  `~/Downloads/agencia_ia_dental_dashboard.zip` siguen desactualizados
  como se anotó en la entrega anterior — no se revisó de nuevo esta vez.
