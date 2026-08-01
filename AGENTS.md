# Agencia IA — Dashboard de KPIs para Clínicas Dentales

## Stack tecnológico

- **Python 3.12** (venv local en 3.12.13). El código usa sintaxis 3.10+ (`X | None`, `int | float`), no corre en 3.9.
- **anthropic 0.120.0** — API de Claude. `MODEL = "claude-sonnet-5"` (constante duplicada por módulo, no compartida: `extractors/excel_parser.py`, `extractors/vision_parser.py`, `interpretacion.py`, `segunda_lectura.py`, `cruces_propuestos.py`). `interpretacion.MODEL_INFORME = "claude-opus-5"` es la ÚNICA llamada en Opus, solo para `interpretar_clinica`.
- **pandas 3.0.5 + openpyxl 3.1.5 + xlrd 2.0.2** — lectura de Excel/CSV.
- **rapidfuzz 3.14.5** con fallback a `difflib` si no está instalada — matching de nombres de pacientes.
- **streamlit 1.60.0** — solo `probar_manual.py` (harness de prueba, NO el producto).
- **python-dotenv 1.2.2** — carga `ANTHROPIC_API_KEY` desde `.env`.
- **No hay `requirements.txt`**: las dependencias reales viven en `venv/` (gitignored). Si se agrega uno, congelar las versiones del venv, no las últimas de PyPI.
- No hay FastAPI, frontend, ni Supabase todavía — intencional. El motor (`pipeline.procesar_migracion`, `resolver_conflicto`) ya está listo y probado para envolverse.

## Convenciones de código

- **Español para todo lo que no sea sintaxis**: variables, funciones, clases, docstrings, comentarios, mensajes de error y nombres de test. Términos técnicos crudos quedan en inglés (`serie`, `payload`, `grid`, `ledger`).
- **Docstrings largos y narrativos que explican el PORQUÉ**: cada módulo abre citando el bug/hallazgo real o la fase que motivó el diseño ("hallazgo 1.3", "Fase H"), decisiones de producto, y qué se descartó. Los comentarios inline siguen la misma regla: solo para lo no obvio.
- **Dataclasses para todo lo estructurado** (`VariableValue`, `MetricaInfo`, `Conflicto`, `KPIFormula`, `Gap`, `Intervencion`, `Diagnostico`, `PatronCruzado`, `Trazabilidad`, `Match`), con comentario por campo cuando el campo tiene una razón sutil (`entidad=None` para no fusionar tratamientos por matching de pacientes).
- **Estados**: en el núcleo los "tipos" son strings literales (`"medido"|"estimado"|"derivado"`, `tipo="cobertura_distinta"`), NO enums. El único `Enum(str, Enum)` es `EstadoEvidencia` en `diagnostico.py` (6 valores).
- **Fallos ruidosos, nunca silenciosos** — patrón central del repo: un dato rechazado no desaparece, sale a una estructura auditable con motivo (`variables_en_cuarentena`, `kpis_con_error`, `conflictos_pendientes`, `Rechazo`, `Discrepancia`). Se prefiere devolver una estructura antes que lanzar una excepción.
- **`None` como "salto local silencioso"** para lo que sí es esperable (denominador 0, propuesta rechazada, período no interpretable) — nunca inventa un valor de reemplazo.
- **El modelo (Claude) nunca hace aritmética**: declara índices/unidad de origen/agregación; toda conversión numérica la hace el código (`FACTORES_CONVERSION`). Regla repetida en varios módulos, no violarla.
- **`thinking` siempre explícito en las llamadas a Claude**: `{"type": "disabled"}` en extractores, `interpretar_kpi` e `interpretar_panel`; `{"type": "adaptive"}` + streaming solo en `interpretar_clinica`. Motivo en `claude_utils.extraer_texto`: omitirlo corre adaptativo y se come el presupuesto de tokens.
- **Funciones puras que no mutan su input** (`reconciliar`, `derivar_variables_faltantes` devuelven colecciones nuevas; el llamador decide).
- **Imports planos** (`from schema import ...`, `import periodos`), sin paquete raíz ni relativos con punto. Ciclos evitados a mano (`FUENTE_DERIVADA` vive en `reconciliacion.py`; `contexto_cualitativo.py` se separó de `interpretacion.py` para romper un ciclo con `diagnostico.py`).
- **Imports opcionales** de librerías pesadas: `try: import anthropic / except ImportError: anthropic = None`, con `assert` + mensaje de instalación al usar.
- **Constantes de config en MAYÚSCULAS a nivel módulo** con comentario de una línea sobre de dónde sale el número (`UMBRAL_EMPATE`, `TOLERANCIA_PCT`, `CONFIANZA_DERIVADA`, `MINIMO_PERIODOS_COMUNES`, `CONFIANZA_PROPUESTA=0.6`).

## Patrones

- **Vocabulario común + fórmulas puras** (`schema.py`): un único diccionario de ~30 variables que alimenta wizard, extractores y las 20 `KPI_FORMULAS`. Habilita la cobertura "por variable, no por KPI".
- **Orquestador puro** (`pipeline.py`): `procesar_migracion` / `resolver_conflicto` reciben paths/dicts y devuelven un dict JSON-serializable, sin ningún import de Streamlit ni framework web. Ese es el contrato con el futuro endpoint de FastAPI.
- **Separación estricta determinista vs. LLM**: `cruces.py`, `diagnostico.py`, `priorizacion.py`, `estacionalidad.py`, `calidad.py`, `agregados.py` NO importan `anthropic` (testeables sin red). La capa que llama a Claude (`cruces_propuestos.py`, `interpretacion.py`, `segunda_lectura.py`, extractores) consume los hechos ya verificados; nunca al revés. Los SYSTEM_PROMPT le piden explícitamente a Claude NO recalcular gaps ni patrones, solo redactarlos.
- **SYSTEM_PROMPT derivado de `schema.py`, nunca hardcodeado**: los extractores inyectan JSON generado desde el schema (`_VARIABLES_JSON`, `_KPIS_PORCENTUALES_JSON`, `_TIPOS_EVENTO_JSON`), filtrando `VARIABLE_TYPES` por `list`/`ledger`.
- **Confianza de valores derivados siempre topeada, nunca inventada**: `min(confianza_a, confianza_b)` en cruces; `min(cruce.confianza, 0.6)` en propuestas; `CONFIANZA_DERIVADA` en derivación.
- **Cuarentena en vez de descarte**: `validacion.py` filtra, `explicaciones.py` traduce el motivo técnico a lenguaje de dueño de clínica SIN tocar los mensajes de `validacion.py` (los tests dependen de ellos).
- **Álgebra dimensional como fuente de verdad** (`cruces.py`): `OPERACIONES_LEGALES[(unidad_a, op, unidad_b)]` es la única autoridad; `monto ÷ conteo` restringido a `DENOMINADORES_VOLUMEN`, `conteo ÷ conteo` confinado al embudo (`ETAPAS_EMBUDO`).
- **Identidad de paciente: la zona gris nunca se fusiona sola** (`matching.py`) — tres umbrales (0.80/0.60/0.90) + compatibilidad de nombre de pila; un match ambiguo va a `conflictos_pendientes` para que el dueño confirme. Un ID estable (`campo_es_id_estable=True`) saltea el matching por completo.
- **Detección de firma en vez de casos especiales hardcodeados** (`pipeline.extraer_archivo` usa `inspect.signature` para decidir si pasar `registro_clientes`).
- **Fuente única de verdad en fixtures** (`evals/`): los valores dorados se derivan de los mismos arrays que escriben los fixtures, para que no se desincronicen.

## Prohibiciones

- **Nunca tocar, leer en logs, ni commitear `parser/datos_clinica_real/`** — datos reales de una clínica (Excel, CSV, foto de paciente). Ya gitignored. No citarlo fuera del repo.
- **Nunca hardcodear `ANTHROPIC_API_KEY`** ni ningún secret — siempre vía `.env`/entorno. No leer ni mostrar el contenido de `.env`.
- **No introducir pytest** ni fixtures de pytest — no está instalado y rompe la convención de los 363 tests standalone.
- **No cambiar los mensajes de `validacion.py`** sin revisar `test_validacion.py` primero — los tests dependen del texto exacto; por eso `explicaciones.py` traduce aparte.
- **No hacer que el modelo calcule ni convierta unidades** en ningún extractor — declarar la unidad de origen y dejar la conversión al código (`FACTORES_CONVERSION`).
- **No fusionar identidades de paciente automáticamente en zona gris** — todo lo ambiguo va a `conflictos_pendientes`.
- **No cargar un benchmark con un rango inventado** — `benchmarks.py` documenta que un rango falso es "peor que no tener benchmark"; cuando la conversión exigiría inventar una cifra, se deja `sin_benchmark`.
- **No agregar un `requirements.txt` con versiones "latest"** — congelar contra el venv.
- **No editar `Preguntas_Diagnostico_Odontologia_v2.docx` ni los `plan_*.md` ejecutados** como borradores — son artefactos de decisión cerrados.

## Estructura de proyecto

```
parser/                          Motor de KPIs — casi todo el código real del repo
  schema.py                      Vocabulario de ~30 variables + las 20 fórmulas de KPI (núcleo)
  coverage.py                    Cobertura por variable + priorización de preguntas del wizard
  conflictos.py                  Resolución de conflictos entre archivos/migraciones
  pipeline.py                    Orquestador — punto de entrada único (procesar_migracion)
  validacion.py                  Guardas de tipo/forma/origen (mensajes ligados a tests, no tocar)
  reconciliacion.py               Compara KPI recalculado contra la tasa ya declarada en la planilla
  derivacion.py                  Completa una variable despejándola de una tasa declarada
  segunda_lectura.py             Segunda opinión de Claude sin contexto, para confianza baja
  claude_utils.py                Helpers de lectura de respuesta de Claude (thinking, truncado)
  extractors/
    excel_parser.py              Excel/CSV: pandas lee crudo, Claude mapea columnas, código calcula
    vision_parser.py             Fotos/PDF: Claude Vision lee y mapea; declara thinking disabled
    __init__.py                  Vacío (los módulos se importan por ruta completa)
  cruces.py                      Métricas derivadas deterministas (embudo + álgebra de unidades)
  cruces_propuestos.py           Capa 3: Claude propone qué cruzar, el código calcula y valida
  calidad.py                     Data Quality Report (completitud/consistencia/confianza)
  agregados.py                   Promedio/mediana/outliers sobre una serie
  formato.py                     Formatea un valor según su unidad para la UI
  trazabilidad.py                Lineage: de qué celda/fórmula/conversión salió cada valor
  periodos.py                    Normaliza etiquetas de período a clave canónica ("2026-04")
  matching.py                    Identidad de pacientes (rapidfuzz + banda gris, nunca fusiona sola)
  ledger.py                      Arma ledger_pacientes desde una hoja transaccional
  metricas_paciente.py           17 métricas de riesgo/valor/ciclo de vida sobre el ledger
  diagnostico.py                 Diagnostic Engine determinista (estado, patrones, contradicciones)
  catalogo_tecnologico.py        ~35 intervenciones de Agencia IA, indexadas por etapa del funnel
  priorizacion.py                Score = gap × impacto × factor_confiabilidad × addressability × suficiencia
  estacionalidad.py              Estacionalidad de Mar del Plata como dato estructurado
  contexto_cualitativo.py        Preguntas cualitativas por KPI (separado para romper ciclo de import)
  preguntas_wizard.py            Texto exacto de la pregunta que ve el dueño por variable faltante
  interpretacion.py              3 entry points: interpretar_kpi / _panel / _clinica (este último en Opus)
  explicaciones.py               Traduce motivos técnicos a lenguaje de dueño de clínica
  benchmarks.py                  13 benchmarks argentinos + cálculo de gap (mejor_es/confiabilidad)
  aranceles_com.py               Arancel del Círculo Odontológico de Mar del Plata (unidad "consulta")
  referencias/                   Research de benchmarks (fuente de benchmarks.py)
  datos_clinica_real/            Datos reales — gitignored, NO TOCAR (ver Prohibiciones)
  evals/                         Casos dorados + runners contra la API real (NO es la suite de tests)
  test_*.py                      26 archivos, 363 tests deterministas, sin pytest, uno por módulo
  probar_manual.py               Harness Streamlit — NO es el producto
  README.md                      Documentación fase por fase — mantener sincronizada con el código
README.md                        Estado real auditado del proyecto
plan_maestro_benchmarks_interpretacion.md / plan_resolucion_conflictos.md   Planes ya ejecutados
CHECKLIST_PROXIMO.md / PROXIMOS_PASOS_TESTING.md   Notas de trabajo pendiente
```

## Flujo de trabajo

- **Flujo por Pull Request (desde 2026-07-31)**: toda feature entra por una rama → PR a `main`, nunca push directo. `main` está protegida y exige el check de CI `test` en verde antes de mergear. El historial viejo era trunk-based sin ramas; ese modo quedó discontinuado. Detalle completo en `CONTRIBUTING.md`.
- **Trabajo organizado en "Fases"** (letradas A–I / numeradas 0–8 según el módulo), cada una documentada como sección propia en `parser/README.md` con qué se encontró → qué se corrigió → con qué evidencia real (datos de clínica, no hipotéticos).
- **Auditar contra el código antes de documentar**: el último commit existe específicamente porque la doc tenía afirmaciones falsas frente al código. No asumir que lo escrito sigue vigente — verificarlo (esta misma generación encontró que `periodo_evaluacion_semanas` ya no queda en `None`).

## Testing, CI/CD

- **CI en `.github/workflows/ci.yml`** (desde 2026-07-31): cada PR/push a `main` corre `ruff check parser` (informativo, no bloqueante) + los 26 tests offline. El job se llama `test` y es el check requerido para mergear. `tests-api.yml` es manual (`workflow_dispatch`) y corre `parser/evals/runner.py` contra la API real (consume créditos). `release-please.yml` maneja el versionado automático.
- **363 tests en 26 archivos `test_*.py`** dentro de `parser/`, uno por módulo, **sin pytest**. Cada archivo corre standalone:
  ```
  python3 test_pipeline.py
  ```
  con el patrón al final: `tests = [v for k,v in list(globals().items()) if k.startswith("test_")]`, itera, llama `test()`, imprime `OK  {nombre}` y el conteo total.
- Tests deterministas, sin red — los módulos que llaman a Claude reciben `client=None` (devuelve el payload crudo) o un cliente falso (`_ClienteFalso`/`SimpleNamespace(create=...)` que captura la última llamada).
- **`parser/evals/` es aparte**: `runner.py` corre el pipeline contra la API real de Claude (necesita `ANTHROPIC_API_KEY`) y compara contra valores dorados con tolerancia porcentual (`_cerca`, 0.5% default) — reporte de precisión, no pass/fail. `runner_diagnostico.py` es determinista y `test_evals_diagnostico.py` lo mete en la suite normal.
- Sin coverage mínimo formal — la métrica trackeada es el conteo de tests verdes (363 al 2026-07-30), reportado en cada actualización de README.

## Estilo de commits y PRs

- **Conventional Commits obligatorios (desde 2026-07-31)**: prefijo `feat:`/`fix:`/`docs:`/`ci:`/`chore:`… lo exige el flujo y release-please usa el prefijo para versionar. El cuerpo puede seguir en español. El historial viejo usa títulos en español sin prefijo (ej. "Cablear el ledger de pacientes…"); ese estilo quedó atrás.
- **Cuerpo largo y denso**, un párrafo por módulo/hallazgo tocado, priorizando el PORQUÉ: qué bug motivó el cambio, con qué dato se confirmó, qué se descartó como premisa.
- **Afirmaciones verificadas, no aspiracionales** — cerrar diciendo qué se verificó ("el conteo de 363 tests coincide con correr la suite ahora mismo").
- **Sin atribución de IA** (`Co-Authored-By`) en los commits.
- **Toda feature vía PR a `main`** — ver la sección "Flujo de trabajo" y `CONTRIBUTING.md`.

## Skills Reference

Para patrones detallados, usá estos skills del proyecto (`.claude/skills/`):
- `parser-nueva-variable` — agregar una variable al vocabulario de `schema.py` y cablearla en todos los lugares acoplados
- `parser-editar-prompt-extractor` — ajustar un SYSTEM_PROMPT o cablear una variable nueva al prompt de un extractor
- `parser-nuevo-cruce-dimensional` — agregar una operación dimensional legal / un tipo de cruce derivado
- `parser-nueva-metrica-paciente` — agregar una métrica al ledger de pacientes (`metricas_paciente.py`)
- `parser-nueva-intervencion-catalogo` — agregar una intervención al catálogo tecnológico
- `parser-editar-benchmark` — agregar/editar un benchmark argentino o el arancel de referencia
- `parser-test-sin-pytest` — escribir un `test_*.py` nuevo siguiendo la convención sin pytest

Skills externas recomendadas de **skills.sh** (instalables con `npx skills add <owner/repo>`; verificadas en su API en vivo). Instalar según la etapa:

_Etapa actual (motor Python):_
- `anthropics/skills/claude-api` — usar la API/SDK de Claude correctamente (modelos, params, tool use). Oficial.
- `anthropics/skills/xlsx` · `anthropics/skills/pdf` · `anthropics/skills/docx` — extracción de documentos. Oficiales.

_Etapa que viene (envolver el motor):_
- `fastapi/fastapi/fastapi` — envolver `pipeline.procesar_migracion` en el endpoint del onboarding.
- `supabase/agent-skills/supabase-postgres-best-practices` — conectar `kpi_snapshots` (hoy hay dos stubs `cargar_/guardar_variables_de_supabase`).
- `czlonkowski/n8n-skills/n8n-workflow-patterns` — workflows de n8n.
- `streamlit/agent-skills/developing-with-streamlit` — si el wizard sigue en Streamlit.

> Nota: las skills de **pytest** de skills.sh NO aplican — la suite es standalone sin pytest. Solo considerarlas si alguna vez se decide migrar.

## Cuándo invocar cada skill

Al realizar estas acciones, invocá SIEMPRE el skill correspondiente primero:

| Acción | Skill |
|---|---|
| Agregar/renombrar una variable en `schema.py` (`VARIABLE_TYPES`, `METRICAS`, `INTERNAL_VARIABLES`, `SOLO_MIGRACION_O_SISTEMA`) | `parser-nueva-variable` |
| Editar un SYSTEM_PROMPT de extractor o cablear una variable al prompt | `parser-editar-prompt-extractor` |
| Agregar una operación a `OPERACIONES_LEGALES` / un tipo de cruce | `parser-nuevo-cruce-dimensional` |
| Agregar una métrica de paciente a `metricas_paciente.py` | `parser-nueva-metrica-paciente` |
| Agregar una intervención a `catalogo_tecnologico.py` | `parser-nueva-intervencion-catalogo` |
| Agregar/editar un valor en `benchmarks.py` o `aranceles_com.py` | `parser-editar-benchmark` |
| Escribir un `test_*.py` nuevo o sumar tests a uno existente | `parser-test-sin-pytest` |
| Agregar un KPI a `KPI_FORMULAS` (toca variables + benchmark + tests) | `parser-nueva-variable` + `parser-editar-benchmark` + `parser-test-sin-pytest` |
