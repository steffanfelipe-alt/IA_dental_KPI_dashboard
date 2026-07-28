# Parser de migración — Agencia IA / Clínicas Dentales

Implementa el Paso 3 del onboarding (sección 5 del Miro) y la tabla de
fórmulas (sección 6 del Miro): recibe lo que el dueño de la clínica sube
(Excel, CSV, fotos, PDF), lo normaliza a un vocabulario común de variables,
calcula los KPIs que ya puede, y devuelve al wizard solo lo que falta —
una vez por variable, nunca una vez por KPI.

## Estructura

```
schema.py                    Vocabulario de ~28 variables + las 20 fórmulas de KPIs
coverage.py                  Chequeo de cobertura por variable + priorización del wizard
conflictos.py                Resolución de conflictos entre archivos/migraciones
pipeline.py                  Orquestador: punto de entrada único (procesar_migracion)
extractors/
  excel_parser.py            Excel/CSV -> Claude mapea columnas ambiguas al vocabulario
  vision_parser.py           Fotos/PDF -> Claude Vision lee y mapea en un solo paso
aranceles_com.py             Arancel del Círculo Odontológico de Mar del Plata (unidad "consulta")
benchmarks.py                13 benchmarks argentinos por KPI + cálculo de gap (ver más abajo)
interpretacion.py            Cruza gap + contexto cualitativo -> interpretación del asistente
priorizacion.py              Motor de priorización: score = gap × impacto × factor_confiabilidad
referencias/
  benchmarks_research_AR.md  Research completo de benchmarks (fuente de benchmarks.py)

trazabilidad.py               Lineage: de qué celda/fórmula salió cada valor (ver explicar())
periodos.py                   Normaliza etiquetas de período a clave canónica ("2026-04")
agregados.py                  Promedio/mediana/suma sobre una serie ya extraída + detección de outliers
matching.py                   Resolución de identidad de pacientes (fuzzy matching + banda gris)
ledger.py                     Arma ledger_pacientes a partir de registros transaccionales ya extraídos
metricas_paciente.py          17 métricas de riesgo/valor/ciclo de vida/atribución sobre el ledger
calidad.py                    Data Quality Report: completitud/consistencia/confianza + suficiencia_datos
contexto_cualitativo.py       Preguntas cualitativas por KPI (extraído de interpretacion.py)
estacionalidad.py             Estacionalidad de Mar del Plata como dato estructurado (proxy sobre P51)
diagnostico.py                Diagnostic Engine: estado de evidencia, patrones cruzados, contradicciones
catalogo_tecnologico.py       ~35 intervenciones reales de Agencia IA, indexadas por etapa del funnel
evals/
  casos_diagnostico.py        Casos sintéticos para el Diagnostic Engine (ver nota de scope, §24)
  runner_diagnostico.py       Precisión de cuello de botella, falsos diagnósticos, % accionables
```

## Uso desde el endpoint de FastAPI

```python
from pipeline import procesar_migracion

@app.post("/onboarding/{clinica_id}/migrar")
async def migrar_datos(clinica_id: str, archivos: list[UploadFile]):
    paths = [guardar_temporalmente(a) for a in archivos]
    variables_previas = cargar_variables_de_supabase(clinica_id)  # kpi_snapshots existentes

    resultado = procesar_migracion(paths, variables_previas=variables_previas)

    guardar_variables_en_supabase(clinica_id, resultado["variables"])
    return {
        "kpis_calculados": resultado["kpis_calculados"],
        "preguntas_wizard": resultado["preguntas_wizard"],   # -> Paso siguiente del onboarding
        "para_confirmar": resultado["variables_a_confirmar"],  # -> pre-cargar como sugerencia, no pregunta abierta
    }
```

Si el dueño no sube nada (Paso 3 es opcional), llamar a `pipeline.sin_archivos()`
en su lugar — corre el mismo chequeo y el wizard termina preguntando el set
completo, sin necesitar un camino de código separado.

### Conflictos entre archivos migrados

Si dos archivos (o una migración anterior + una nueva) dan valores distintos
para la misma variable, `pipeline.procesar_migracion` ya no elige por orden
de llegada: los delega a `conflictos.resolver_conflictos`. Regla aplicada:

- Mismo valor en todos los candidatos → no hay conflicto.
- Confianzas separadas por ≥ `conflictos.UMBRAL_EMPATE` (0.1) → gana la de
  mayor confianza, automático.
- Confianzas empatadas o casi → conflicto real: la variable no se calcula
  en ningún KPI (aparecen en `kpis_esperando_resolucion_conflicto`, no en
  `kpis_parciales` ni en `preguntas_wizard`) y se agregan a
  `conflictos_pendientes` para que el dueño elija.

El wizard necesita una pantalla nueva para esto (tarjeta de conflicto:
"Excel_turnos.xlsx dice 56" / "Foto_cuaderno.jpg dice 60", con opción de
cargar un tercer valor) — no es la misma UI que "completá este dato".

Endpoint sugerido para resolver un conflicto (mismo patrón que el de arriba):

```python
from pipeline import resolver_conflicto

@app.post("/onboarding/{clinica_id}/resolver-conflicto")
async def resolver_conflicto_endpoint(clinica_id: str, body: dict):
    # body: {"variable": "no_shows", "valor": 13, "fuente_elegida": "migracion_excel"}
    #    o: {"variable": "no_shows", "valor_manual": 15}
    variables_previas = cargar_variables_de_supabase(clinica_id)
    resultado = resolver_conflicto(
        body["variable"], variables_previas,
        valor=body.get("valor"), valor_manual=body.get("valor_manual"),
    )
    guardar_variables_en_supabase(clinica_id, resultado["variables"])
    return resultado
```

Una vez que el dueño confirma, esa variable queda con
`fuente == "confirmado_por_dueno"` y gana siempre frente a cualquier archivo
nuevo que la contradiga — **salvo** que el archivo nuevo también la
contradiga, caso que hoy no reabre un conflicto (ver `TODO` en
`conflictos.resolver_conflictos`, fuera de alcance del plan original).

## Cómo se prueba sin la API

`coverage.py`, `schema.py` y `conflictos.py` no dependen de Claude — son
lógica pura sobre diccionarios de `VariableValue`. Se puede (y conviene)
testear el motor de priorización con datos sintéticos antes de conectar
los extractores reales. Corriendo `python3 test_conflictos.py` (sin
pytest) se ven los casos de conflicto; para cobertura, un escenario manual
con un conflicto sin resolver:

```python
from coverage import VariableValue, evaluar_cobertura, variables_para_wizard
from conflictos import resolver_conflictos

fuentes = [
    {"turnos_agendados": VariableValue(200, "migracion_excel", 0.9),
     "no_shows": VariableValue(56, "migracion_excel", 0.8)},
    {"no_shows": VariableValue(60, "migracion_foto", 0.75)},  # confianza casi empatada
]
variables, conflictos = resolver_conflictos(fuentes)
# conflictos == [Conflicto(variable="no_shows", candidatos=[...])]
# "no_shows" no está en `variables`, así que el KPI 4 (tasa de no-show) no
# se calcula ni aparece como pregunta nueva del wizard.

resultado = evaluar_cobertura(variables, variables_en_conflicto={c.variable for c in conflictos})
assert 4 not in resultado.kpis_calculados
assert 4 in resultado.kpis_esperando_resolucion_conflicto
assert not any(p["variable"] == "no_shows" for p in variables_para_wizard(resultado))
```

### Benchmarks argentinos + interpretación del asistente

De los 20 KPIs, 13 se comparan contra un benchmark (los otros 7 son
financieros/internos, dependen 100% del historial propio — ver
`SOLO_MIGRACION_O_SISTEMA` e `INTERNAL_VARIABLES` en `schema.py`). El
research completo (`referencias/benchmarks_research_AR.md`) encontró que
**11 de los 13 son proxy internacional**, no dato argentino — el sistema
tiene que ser honesto sobre eso en cada pantalla y cada respuesta.

```python
from benchmarks import calcular_gap

gap = calcular_gap(kpi_id=4, valor_clinica=28)  # no-show del 28%
# Gap(direccion="por_encima", favorable=False, magnitud_pct=..., ...)
# favorable=False porque KPI 4 tiene mejor_es="menor": estar por encima es malo.
```

- **`favorable`** en `Gap` es lo que le dice al asistente si un gap es
  buena o mala noticia — antes `direccion` ("por_encima"/"por_debajo") no
  alcanzaba, porque para no-show estar arriba es malo pero para
  aceptación estar arriba es bueno.
- **Ticket promedio (KPI 6)** se guarda como múltiplo de "consulta"
  (`es_multiplo_arancel=True`) en vez de un monto fijo en ARS, para no
  desactualizarse por inflación. `calcular_gap` lo resuelve contra
  `aranceles_com.ARANCEL_COM["consulta"]` en cada llamada — actualizar
  ese único número cuando el Círculo publique un arancel nuevo revaloriza
  todo solo.
- **KPIs 7, 10 y 19** (`sin_benchmark`): no hay proxy confiable, así que
  no se compara — mejor sin comparación que con una falsa.
- **KPIs 12 y 15** tienen proxy citable (`confiabilidad="proxy_internacional"`)
  pero sin rango numérico cargado: convertirlos a un número accionable
  exigiría inventar un tipo de cambio (KPI 12) o tratar una estimación
  regional no auditada como cifra dura (KPI 15). La `nota` del benchmark
  igual llega al asistente para que lo mencione como orientación.

`interpretacion.py` cruza ese gap con el contexto cualitativo de la Guía
de Diagnóstico (preguntas que no alimentan ninguna fórmula, pero explican
el porqué) y con el eje temporal — `peso_benchmark_vs_historial` baja el
peso del benchmark externo a medida que la clínica acumula su propio
historial en `kpi_snapshots`:

```python
from interpretacion import interpretar_kpi

interpretar_kpi(
    kpi_id=4, valor_clinica=28,
    respuestas_diagnostico={"P51": "en enero-febrero se complica más"},
    semanas_de_datos_propios=2,   # recién arrancando: pondera 0.8 benchmark / 0.2 historial
)
```

`priorizacion.py` implementa el motor de priorización (score = gap ×
impacto) que antes solo estaba diagramado en el Miro, con el agregado de
`factor_confiabilidad`: un gap grande contra un proxy débil no debe
rankear por encima de un gap mediano contra un dato oficial.

## Decisiones de diseño a tener en cuenta

- **Cobertura por variable, no por KPI.** Si `pacientes_reactivados` falta,
  se pregunta una sola vez aunque la necesiten dos KPIs (9 y 19). El wizard
  ordena las preguntas por cuántos KPIs desbloquea cada variable.
- **Confianza por variable, no por archivo.** Una foto puede dar un dato
  con confianza alta (una tabla impresa clara) y otro con confianza baja
  (un número manuscrito ambiguo) en la misma imagen — se maneja por
  variable individual, no como un score único del archivo.
- **Variables internas nunca se piden.** `automatizaciones_activas`,
  `tareas_manuales_detectadas` y `horas_semana_serie_historica` alimentan
  los KPIs 16 y 17 pero las calcula el propio sistema (comparación
  antes/después). Si faltan, el KPI queda en `kpis_bloqueados_por_diseno`,
  no en la lista de preguntas al dueño.
- **7 KPIs financieros no tienen pregunta en la Guía de Diagnóstico**
  (throughput, producción por hora-sillón, tasa de cobro, LTV, costo de
  adquisición/reactivación, rentabilidad por tratamiento) — por diseño,
  dependen de facturas migradas o carga numérica, nunca de una pregunta
  verbal. Es normal que queden vacíos hasta que la clínica cargue sus
  primeras facturas; comunicarlo así en el panel de resultados.

## Trazabilidad, períodos e identidad de pacientes (Fases 0-2)

- **`trazabilidad.py`**: cada `VariableValue` puede traer un
  `Trazabilidad` opcional (celda/fila/columna, agregación, conversión de
  unidad aplicada). `trazabilidad.explicar(vv)` da el texto legible — un
  "390 min" deja de ser un número sin origen y pasa a ser "6.5 horas × 60
  (hoja Operativo, fila 3)". `kpis_calculados` en el payload de
  `pipeline.procesar_migracion` ya incluye `trazabilidad_legible` por
  variable.
- **`periodos.py`**: dos archivos que etiquetan el mismo mes distinto
  ("Abril 2026" vs "2026-04") ahora intersectan en
  `coverage._calcular_serie_kpi` — antes esa serie se caía a `None` en
  silencio. `VariableValue.etiquetas_originales` conserva la etiqueta
  cruda para mostrar sin perder la clave canónica.
- **`agregados.py`**: `kpis_calculados[id]["agregados"]` trae
  promedio/mediana/último al lado de `"valor"` (que sigue siendo el
  período vigente — el promedio nunca lo reemplaza).
- **`matching.py`**: resuelve "Juan Pérez" / "J. Perez" / "Juan Pérez
  Gómez" al mismo paciente. Usa `rapidfuzz` si está instalada (con
  fallback a `difflib`), pero un solo fuzzy score no alcanza — ver el
  docstring del módulo para el hallazgo real ("Juan Perez" vs "Juana
  Perez" da ~95% de similitud y son personas distintas) y por qué la
  decisión de fusión depende también de si el nombre de pila es
  compatible, no solo del score. Los casos de zona gris nunca se
  fusionan solos: aparecen en `conflictos_pendientes` (variable
  `"identidad_paciente"`) para que el dueño confirme.
- **`ledger.py` + `metricas_paciente.py`**: `ledger_pacientes`
  (`{paciente_id: [eventos]}`) es el insumo de 17 métricas que las 20
  fórmulas de `schema.py` no pueden expresar (no-show recurrente por
  paciente, LTV real, concentración de ingresos, retención por cohorte,
  etc. — ver el docstring de `metricas_paciente.py` para la lista
  completa). **Importante**: hoy ningún extractor en vivo arma
  `ledger_pacientes` automáticamente desde una hoja real — eso requiere
  extender el contrato del `SYSTEM_PROMPT` de `excel_parser.py` para que
  Claude identifique columnas de nombre+fecha+tipo en una hoja
  transaccional, cambio que necesita validarse contra la API real antes
  de confiar en él. `construir_ledger_pacientes` ya está listo para
  cuando esa extracción se conecte; mientras tanto, `_agregar_dict` SÍ
  está enganchado al matching real para `ingreso_por_paciente` (pasando
  `registro_clientes` a `aplicar_mapeo`), que es lo que corrige el LTV
  subestimado del punto 3 del informe de deficiencias sin depender de
  ese contrato nuevo.

## Diagnostic Engine (Fase 4)

`diagnostico.py` se inserta entre `priorizacion.py` e `interpretacion.py`:
estructura qué sabe el sistema (`EstadoEvidencia`: HEALTHY/NORMAL/WATCH/
PROBLEM/CRITICAL/INSUFFICIENT_EVIDENCE), qué patrones cruzados detecta
entre KPIs (`PATRONES_CRUZADOS` — ya no viven como prosa en el prompt) y
qué contradicciones encuentra entre lo que el dueño declaró y lo que los
datos muestran (`detectar_contradicciones`). Es 100% determinista, no
llama a Claude — `interpretacion.interpretar_kpi`/`interpretar_panel`
aceptan un `diagnostico` opcional que viaja en el payload como hechos ya
verificados, no como algo que el modelo tiene que re-derivar.

`construir_contexto_cualitativo` y las tablas de preguntas por KPI se
movieron a `contexto_cualitativo.py` (antes vivían en `interpretacion.py`)
para romper el import circular con `diagnostico.py`, que también las
necesita — `interpretacion.py` las sigue re-exportando, nada que la
importaba desde ahí se rompió.

## Catálogo tecnológico y priorización extendida (Fases 5-6)

`catalogo_tecnologico.py` mapea cada diagnóstico a intervenciones reales
del catálogo de Agencia IA (~35, en 7 etapas de funnel: Captación →
Conversión → Confirmación → Consulta → Post-consulta → Fidelización →
Referidos), incluyendo 3 alternativas de **proceso** (no solo tecnología,
ver §14 del Documento Maestro) y `calcular_addressability` (¿esta
intervención es entregable dado lo que la clínica ya tiene integrado?).

`priorizacion.calcular_score` ahora acepta `addressability` y
`suficiencia` (default 1.0, no rompe ninguna llamada existente) — un
problema grande pero sin intervención entregable o medido con una
variable derivada no debería rankear por encima de uno con camino de
solución claro y datos observados. `priorizar_oportunidades` cablea todo
`diagnostico.py` → `catalogo_tecnologico.py` → `priorizacion.py`, y
`pipeline.procesar_migracion` lo ejecuta automáticamente si se le pasa
`respuestas_diagnostico` (opcional — sin eso, `"diagnostico"` y
`"oportunidades_priorizadas"` quedan en `None`, comportamiento idéntico
al de antes de estas fases).

**Pendiente de tu input** (no bloquea nada, pero está sin completar):
`Intervencion.periodo_evaluacion_semanas` queda en `None` en las ~35
intervenciones — cuántas semanas darle a cada una antes de medir si movió
el KPI no es inventable. Y "reputación" (pedido de reseña) sigue
aproximado con KPI 10 en vez de tener variable propia — el catálogo mismo
lo marca como no mapeado 1:1.

## interpretar_clinica y evals del Diagnostic Engine (Fases 7-8)

`interpretacion.interpretar_clinica` es el tercer entry point (junto a
`interpretar_kpi` e `interpretar_panel`): arma el informe jerárquico de 10
secciones (resumen ejecutivo → mapa del funnel → cuellos de botella →
evidencia → causas → contradicciones → oportunidades tecnológicas → plan
de acción → detalle de KPIs) a partir de lo que ya calcularon
`diagnostico.py` + `catalogo_tecnologico.py` + `priorizacion.py`. El
`SYSTEM_PROMPT_CLINICA` le pide explícitamente a Claude que NO recalcule
gaps ni reinvente patrones — que los repita y explique.

`evals/runner_diagnostico.py` corre el motor determinista completo contra
casos sintéticos (`evals/casos_diagnostico.py`) y reporta precisión de
cuello de botella, tasa de falsos diagnósticos, y % de recomendaciones
accionables. **Importante**: son casos sintéticos, no la validación real
que pide el §24 del Documento Maestro (casos reales anonimizados +
diagnóstico de un experto humano) — eso es un proceso que requiere datos
de clínicas reales y un experto disponible, ninguno de los dos existía en
esta sesión. `test_evals_diagnostico.py` corre los mismos casos como
parte de la suite de regresión (es 100% determinista, no llama a Claude).

## Pendiente

- ~~Reemplazar el placeholder `"claude-sonnet-4-6"` por el string de modelo
  vigente al momento de deployar.~~ Hecho 2026-07-27: `MODEL = "claude-sonnet-5"`
  en `interpretacion.py`, `extractors/excel_parser.py` y
  `extractors/vision_parser.py`.
- Conectar `cargar_variables_de_supabase` / `guardar_variables_en_supabase`
  con la tabla `kpi_snapshots` real.
- Definir qué pasa cuando un archivo nuevo contradice una variable que el
  dueño ya confirmó vía `/resolver-conflicto` (hoy gana la confirmación
  previa en silencio — ver `TODO` en `conflictos.resolver_conflictos`).
- KPIs `sin_benchmark` (7, 10, 19) no entran al ranking numérico de
  `priorizacion.py` (no tienen gap contra el cual medir) — ver `TODO` en
  `priorizacion.py`. Priorizarlos por tendencia propia es una extensión
  que el plan maestro de benchmarks no especificó en fórmula.
- Si aparece una encuesta/informe de FOA, CORA, COMP o una muestra de
  5-10 clínicas de Mar del Plata con datos reales de gestión, reemplazar
  los proxies internacionales en `benchmarks.py` y subir `confiabilidad`
  (ver Recomendaciones en `referencias/benchmarks_research_AR.md`).
- `interpretacion.interpretar_kpi` nunca se probó contra la API real
  (client=None por defecto en los tests) — falta validar con una key de
  Anthropic que el criterio "mismo valor, contextos opuestos -> distinta
  interpretación" se sostiene en la salida del modelo, no solo en el
  payload que se le manda.
- **Extraer `ledger_pacientes` en vivo desde una hoja transaccional real**:
  extender el `SYSTEM_PROMPT` de `excel_parser.py` para que Claude
  identifique columnas de nombre/fecha/tipo/monto/tratamiento en una hoja
  transaccional, y validar ese cambio de contrato contra la API real
  (evals nuevos, no solo los deterministas). Hoy `ledger.py` y
  `metricas_paciente.py` están completos y probados, pero alimentados a
  mano — nada en el pipeline arma el ledger todavía desde un archivo real.
- Nueva dependencia: **`rapidfuzz`** (matching.py). El venv del proyecto
  no traía `pip` funcionando — hubo que arrancarlo con
  `python3 -m ensurepip --upgrade` antes de poder instalarla. No hay
  `requirements.txt` en el repo; si se agrega uno, `rapidfuzz` tiene que
  quedar ahí.
- **Validación real del Diagnostic Engine (§24 del Documento Maestro)**:
  hoy solo hay casos sintéticos (`evals/casos_diagnostico.py`). Falta el
  circuito real — casos anonimizados de clínicas reales, diagnóstico de
  un experto humano, comparación, y ajuste de reglas/benchmarks/prompt
  según esa comparación — antes de confiar en el motor en producción.
- **`Intervencion.periodo_evaluacion_semanas`** queda en `None` en las
  ~35 intervenciones del catálogo — pendiente de confirmar con el usuario
  cuántas semanas darle a cada una antes de medir impacto.
- **"Reputación"** (pedido de reseña) sigue aproximado con KPI 10 en vez
  de tener variable propia — pendiente de decisión.
