# Parser de migración — Agencia IA / Clínicas Dentales

Implementa el Paso 3 del onboarding (sección 5 del Miro) y la tabla de
fórmulas (sección 6 del Miro): recibe lo que el dueño de la clínica sube
(Excel, CSV, fotos, PDF), lo normaliza a un vocabulario común de variables,
calcula los KPIs que ya puede, y devuelve al wizard solo lo que falta —
una vez por variable, nunca una vez por KPI.

## Estructura

32 módulos (30 de primer nivel + 2 extractores), agrupados por función:

```
# Núcleo
schema.py                    Vocabulario de ~28 variables + las 20 fórmulas de KPIs
coverage.py                  Chequeo de cobertura por variable + priorización del wizard
conflictos.py                Resolución de conflictos entre archivos/migraciones
pipeline.py                  Orquestador: punto de entrada único (procesar_migracion)
validacion.py                Guardas de tipo/forma/origen sobre cada variable extraída
reconciliacion.py            Compara el KPI recalculado contra la tasa que la planilla ya declaraba
derivacion.py                Completa una variable ausente despejándola de una tasa declarada
segunda_lectura.py           Segunda opinión de Claude, sin contexto del primer mapeo, para confianza baja

# Extractores
extractors/
  excel_parser.py            Excel/CSV -> Claude mapea columnas ambiguas al vocabulario
  vision_parser.py           Fotos/PDF -> Claude Vision lee y mapea en un solo paso
claude_utils.py              Helpers compartidos: extraer_texto (saltea bloques de thinking)

# Cruces y calidad del dato
cruces.py                    Métricas derivadas fuera de las 20 KPIFormula (embudo + álgebra de unidades)
cruces_propuestos.py         El modelo propone qué cruzar; nunca calcula el número
calidad.py                   Data Quality Report: completitud/consistencia/confianza + suficiencia_datos
agregados.py                 Promedio/mediana/suma sobre una serie ya extraída + detección de outliers
formato.py                   Formatea un valor según su unidad (ARS, %, horas) para la UI

# Trazabilidad e identidad
trazabilidad.py               Lineage: de qué celda/fórmula salió cada valor (ver explicar())
periodos.py                   Normaliza etiquetas de período a clave canónica ("2026-04")
matching.py                   Resolución de identidad de pacientes (fuzzy matching + banda gris)
ledger.py                     Arma ledger_pacientes a partir de una hoja transaccional real
metricas_paciente.py          17 métricas de riesgo/valor/ciclo de vida/atribución sobre el ledger

# Diagnóstico y catálogo
diagnostico.py                Diagnostic Engine: estado de evidencia, patrones cruzados, contradicciones
catalogo_tecnologico.py       ~35 intervenciones reales de Agencia IA, indexadas por etapa del funnel
priorizacion.py               Motor de priorización: score = gap × impacto × factor_confiabilidad
estacionalidad.py             Estacionalidad de Mar del Plata como dato estructurado (proxy sobre P51)
contexto_cualitativo.py       Preguntas cualitativas por KPI (extraído de interpretacion.py)
preguntas_wizard.py           Texto exacto de la pregunta que ve el dueño por cada variable faltante

# Interpretación y explicación
interpretacion.py             Cruza gap + contexto cualitativo -> interpretación del asistente
explicaciones.py              Traduce motivos técnicos (cuarentena/derivada/reconciliación) a lenguaje llano

# Benchmarks
benchmarks.py                 13 benchmarks argentinos por KPI + cálculo de gap (ver más abajo)
aranceles_com.py              Arancel del Círculo Odontológico de Mar del Plata (unidad "consulta")
referencias/
  benchmarks_research_AR.md   Research completo de benchmarks (fuente de benchmarks.py)

# Harness de prueba (no es el producto — ver nota más abajo)
probar_manual.py              Streamlit: sube archivos, corre pipeline.py, muestra cada sección del payload

# evals/
evals/
  casos_diagnostico.py        Casos sintéticos para el Diagnostic Engine (ver nota de scope, §24)
  runner_diagnostico.py       Precisión de cuello de botella, falsos diagnósticos, % accionables
```

**`probar_manual.py` no es el producto.** Es el harness con el que se prueba
`pipeline.procesar_migracion` a mano (subir archivo, ver el payload completo, resolver
conflictos con un click) — corre en una sola sesión de Streamlit, sin auth ni multi-clínica.
La lógica que sí está lista para producto (`procesar_migracion`, `resolver_conflicto`) es
pura: recibe paths y dicts, devuelve un payload JSON-serializable, sin ningún import de
Streamlit — ver "Uso desde el endpoint de FastAPI" más abajo.

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
nuevo que la contradiga. La confirmación sigue ganando siempre (no se pierde
el trabajo previo), pero desde la Fase H **ya no pasa en silencio**: si un
archivo nuevo trae un valor distinto, se genera un `Conflicto` con
`tipo="contradice_confirmado"` para que el dueño sepa que algo no cierra
(ver `conflictos.resolver_conflictos`).

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
  `"identidad_paciente"`) para que el dueño confirme. **No se llama en
  absoluto cuando el identificador ya es estable** (ver
  `campo_es_id_estable` abajo) — un ID como `"P1045"` no necesita fuzzy
  matching, y pasarlo igual por ahí demostró fusionar en silencio
  identificadores como `"Paciente 1"`/`"Paciente 2"`/`"Paciente 3"`.
- **`ledger.py` + `metricas_paciente.py`**: `ledger_pacientes`
  (`{paciente_id: [eventos]}`) es el insumo de 17 métricas que las 20
  fórmulas de `schema.py` no pueden expresar (no-show recurrente por
  paciente, LTV real, concentración de ingresos, retención por cohorte,
  etc. — ver el docstring de `metricas_paciente.py` para la lista
  completa). **`ledger_pacientes` ya se arma en vivo** (Fase H):
  `extractors/excel_parser.py` declara un bloque `"ledger"` en el
  `SYSTEM_PROMPT` para hojas `orientacion="transaccional"`, y
  `construir_ledger_pacientes` recibe `campo_es_id_estable: bool = False`
  — con `True`, bypassea `matching.py` por completo y usa el valor de la
  columna directo como `cliente_id` (el camino real: un CSV de cobros con
  `id_paciente` ya canónico). `ingreso_por_paciente` se deriva de
  `metricas_paciente.ltv_real` cuando hay un ledger con eventos `pago`,
  desbloqueando KPI 14 — ver la sección "Ledger de pacientes y KPI 14
  (Fase H)" más abajo para el detalle completo, incluido el bug de fusión
  silenciosa que motivó `campo_es_id_estable`.

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

## Cruces determinísticos y propuestos (Fases B/C/F)

`cruces.py` calcula métricas fuera de las 20 `KPIFormula` fijas, en dos
capas deterministas sin API: la capa de embudo (toda razón
etapa-posterior/etapa-anterior es una conversión válida por construcción,
vía `ETAPAS_EMBUDO`) y la capa de álgebra de unidades (análisis dimensional
puro sobre `OPERACIONES_LEGALES` — `monto_ars ÷ conteo`, `conteo ÷ horas`,
etc.). Nunca importa `anthropic`, así que sigue siendo testeable sin red.

`cruces_propuestos.py` es la capa 3: el modelo **propone** qué cruzar y por
qué le importaría al dueño (etapa del embudo + cómo ayuda a decidir), pero
nunca calcula el número — cada propuesta pasa por `cruces.calcular_cruce`
(el mismo motor de la capa 1/2) y por una validación dimensional propia.
Confianza topeada en 0.6, igual que cualquier valor derivado. En
`probar_manual.py` (sección 9b) el dueño acepta o descarta cada propuesta
con un click; la aceptada se fusiona con la tabla de cruces confirmados de
la sección 9, indistinguible de uno determinístico.

Bug encontrado y corregido en el camino: Streamlit interpreta `$...$` como
fórmula LaTeX, así que un monto en ARS dentro de un `st.markdown` (ej. "la
serie histórica: 2026-01: $100.000, 2026-02: ...") se deformaba en
pantalla. Se escapa el `$` en los 4 puntos donde un monto entra a un
contexto markdown.

## Arreglos de confiabilidad (Fase G)

Auditoría contra archivos reales de una clínica (Excel + CSV), cinco
defectos encontrados y corregidos, ninguno introducido por las fases
anteriores:

- **Trazabilidad que se perdía al fusionar series** (`_resolver_por_periodo`
  en `conflictos.py`): guardaba sólo `fuente`/`confianza` del ganador de
  cada período y descartaba `archivo_origen`, `trazabilidad`,
  `etiquetas_originales` — 7 de 9 variables mostraban "sin traza
  registrada" en la sección 2a aunque sí tuvieran origen. Corregido
  guardando el `VariableValue` completo del ganador, no sólo dos campos.
- **`max_tokens` insuficiente** en `interpretar_kpi` (800→2500) e
  `interpretar_panel` (2000→12000) — ambos truncaban con datos reales.
- **`costo_hora_sillon` declarada con la unidad equivocada**: era
  `monto_ars`, pasó a `monto_ars/hora` (la definición siempre fue una
  tarifa horaria) — esto solo elimina cruces sin sentido, sin escribir
  ningún filtro nuevo.
- **Whitelist de denominadores con sentido** (`DENOMINADORES_VOLUMEN` en
  `schema.py`): un cruce `monto ÷ conteo` sólo se genera si el conteo
  representa volumen de trabajo real (turnos, pacientes) — antes
  `no_shows` podía terminar de denominador de un monto, sin sentido de
  negocio.
- **`resolver_conflicto` vaciaba el diagnóstico al resolver un conflicto**:
  no reenviaba `respuestas_diagnostico` a `procesar_migracion`, así que el
  dueño ganaba un KPI y perdía todo el diagnóstico/oportunidades en el
  mismo movimiento. Corregido, y cableado a la UI (sección 4) con un
  botón real de resolución.
- **`estacionalidad.py` cableado a `diagnostico.py`**: daba una señal
  determinista de temporada en vez de depender de que el modelo se
  acordara de aplicarla desde el prompt.
- **Opus 5 sólo para el informe largo** (`interpretar_clinica`) — los
  otros dos entry points (`interpretar_kpi`, `interpretar_panel`) siguen
  en Sonnet 5, es el único que corre con thinking adaptativo y arma las
  10 secciones.

## Ledger de pacientes y KPI 14 (Fase H)

**El hallazgo que cambió el diseño del ledger.**
`ledger.construir_ledger_pacientes` pasaba el identificador de paciente
por `matching.encontrar_o_crear_cliente` (matching difuso de nombres). Con
identificadores ya canónicos como `"Paciente 1"`/`"Paciente 2"`/`"Paciente
3"` (comparten token + similitud 0.90, por encima del umbral de fusión
automática), el sistema los fusionaba **en un solo cliente, en silencio**
— justo lo que `matching.py` promete no hacer nunca. Causa raíz: un ID ya
canónico no necesita pasar por matching difuso, que existe para el
problema real de "Juan Pérez" vs "J. Perez". Arreglo: parámetro nuevo
`campo_es_id_estable: bool = False` — con `True`, bypassea `matching.py`
por completo y usa el valor de la columna directo como `cliente_id`.

**`ledger_pacientes` ya se arma en vivo.** `extractors/excel_parser.py`
declara un bloque `"ledger"` en el `SYSTEM_PROMPT` para hojas
`orientacion="transaccional"` (columna de paciente + si es un ID estable,
fecha, tipo de evento por `ledger.TIPOS_EVENTO`, monto y tratamiento
opcionales) — una fila puede generar más de un evento (ej. un presupuesto
aceptado es `presupuesto_emitido` **y** `presupuesto_aceptado`). Si más de
un archivo de la misma migración aporta ledger, se fusionan por paciente
en `pipeline.py` antes de `resolver_conflictos` (un ledger nunca compite
por igualdad de valor — dos archivos con historial de paciente aportan
eventos distintos, no versiones contradictorias del mismo dato).

**KPI 14 (Valor del paciente / LTV) queda desbloqueado**:
`pipeline.py` deriva `ingreso_por_paciente` con `metricas_paciente.ltv_real`
cuando hay un ledger con eventos `pago` — verificado con datos reales:
160 pacientes en el ledger, KPI 14 calculado en $288.584, y
`concentracion_ingresos` mostrando que el top 10% de pacientes genera el
32,5% de la facturación. `probar_manual.py` tiene una sección 10 nueva con
las 17 métricas de `metricas_paciente.py` (no-show recurrente, LTV,
concentración de ingresos, retención por cohorte, etc.), separada de los
KPIs — nunca se mezclan, un cruce/métrica de paciente no tiene `kpi_id`.

**Bug real encontrado con datos reales, no hipotético**:
`periodos.normalizar_periodo` rechazaba cualquier fecha con componente de
hora (`"2024-08-03 09:30:00"`, el timestamp típico de un export de
sistema real) — silenciaba 643 filas completas de un CSV de cobros sin
ningún aviso. Arreglado en el origen (`_fecha_desde_etiqueta` tolera un
sufijo de hora opcional), no parcheado en el punto de uso — la misma
función la usa `excel_parser._construir_serie_periodo`, así que el bug
afectaba a cualquier hoja con fecha+hora, no sólo al ledger.

`vision_parser.py` corrió por primera vez contra la API real (nunca tenía
tests ni se había probado): ahora declara `thinking={"type": "disabled"}`
(antes podía truncarse sin dejar texto), un item mal formado del modelo ya
no tira abajo el lote entero, y dejó de ofrecer el tipo `"ledger"` en su
vocabulario (una foto no puede producir un dict de listas).

## Que el sistema se explique (Fase I)

Fase que salió de usar el sistema de punta a punta por primera vez con los
4 archivos reales juntos (Excel + 2 CSV + 1 foto) — no de una revisión de
código.

- **`explicaciones.py`** (nuevo): traduce los motivos técnicos de
  cuarentena/derivada/reconciliación a lenguaje de dueño de clínica.
  `validacion.py` no cambió sus mensajes (los tests dependen de ellos) —
  el módulo nuevo vive aparte y traduce sin tocar la fuente.
- **El catálogo tecnológico recomendaba mal**: `calcular_addressability`
  penalizaba una intervención por si su descripción contenía la palabra
  "API" o "sistema" (keyword-match sobre texto libre), no por mérito real
  — un chatbot de respuesta instantánea quedaba sistemáticamente último
  frente a alternativas peor etiquetadas que zafaban por redacción. Campo
  explícito `requiere_integracion` en `Intervencion` reemplaza la
  heurística. Además, una intervención sólo podía atacar un `kpi_objetivo`
  — un agente de agendamiento 24/7 nunca podía proponerse para "tiempo de
  primera respuesta" aunque también lo resuelva; `kpis_secundarios` lo
  permite.
- **El informe de clínica no veía la calidad real del dato**:
  `interpretar_clinica` sólo recibía `calidad_datos` (4 números
  agregados), nunca las cuarentenas, discrepancias, derivadas ni
  conflictos reales — aunque el propio prompt le pide hablar de "dónde el
  dato no alcanza o contradice lo declarado". Ahora recibe las cuatro
  claves con los motivos ya traducidos por `explicaciones.py`.
- **Los conflictos no explicaban de dónde salía cada número**:
  `conflictos._candidato()` armaba un dict de 4 claves y descartaba serie,
  trazabilidad y período — la UI no podía mostrar la cuenta porque nunca
  la recibía. Ahora cada candidato trae la explicación completa (vía
  `trazabilidad.explicar()`) y su serie si la tiene.
- **Resolver un conflicto ya no obliga a elegir uno solo, ni destruye la
  serie**: `resolver_conflicto` construía siempre un `VariableValue`
  escalar pelado, así que elegir el candidato con 6 meses de historia
  perdía esos 6 meses. `conflictos.fusionar_candidatos()` (nuevo) fusiona
  dos candidatos con serie por período, o pide a qué período asignar un
  escalar sin fecha — y preserva la serie incluso eligiendo un solo
  candidato. De paso se corrigió un bug latente: `_resolver_por_periodo`
  tomaba el "último período" por orden de aparición en los candidatos, no
  cronológico.

## Catálogo de intervenciones ampliado — procesos sin IA y captación (2026-07-31)

Se encontró: 4 de las 7 etapas del embudo (`captacion`, `conversion`, `consulta`,
`post_consulta`) no tenían ninguna alternativa `tipo="proceso"` (sin IA) en
`catalogo_tecnologico.py` — todas sus intervenciones eran tecnológicas. Además, las 4
intervenciones de `captacion` sólo atendían leads que ya existían; ninguna generaba tráfico
nuevo (nada de Meta Ads, Google Ads ni SEO). Y el KPI más cercano a "captación" (KPI 1,
consultas nuevas/mes) no tenía entrada en `BENCHMARKS_AR`.

Se corrigió: 10 intervenciones nuevas (`INTERVENCIONES` pasa de 35 a 45) — 4 de captación
(Meta Ads y Google Ads ancladas a KPI 19 costo de adquisición con KPI 1 volumen como
secundario, por ser canales pagos; SEO y Google Business Profile ancladas a KPI 1 con KPI 19
como secundario, por ser orgánicos) y 6 de proceso sin IA repartidas 1/2/2/1 en
captación/conversión/consulta/post-consulta. Se agregó KPI 1 a `BENCHMARKS_AR` como
`sin_benchmark` (mismo patrón que KPI 7/10/19: `rango_bajo`/`rango_alto=None`) — decisión
explícita de NO inventar un número, porque es un conteo crudo y no hay benchmark universal que
sirva igual para una clínica chica que para una grande sin normalizar por tamaño.

Con qué evidencia: los 26 `test_*.py` (363 tests) siguen en verde, incluidos los tres asserts
hardcodeados que dependían del conteo anterior (`test_catalogo_tecnologico.py`:
intervenciones 35→45, procesos 3→9; `test_benchmarks.py`: tupla `sin_benchmark` `(7,10,19)` →
`(1,7,10,19)`). Diff acotado: ~122 líneas.

## Pendiente

**363 tests verdes** al momento de escribir esto (2026-07-31) — el número sigue subiendo
fase a fase, no tomarlo como techo.

### Pendientes reales de la Fase I

1. **I6 — CONFIRMADO (2026-07-31)**: el `SYSTEM_PROMPT` de hojas transaccionales se reforzó
   para que declarar `columna_periodo` sea imperativo cuando hay columna de fecha (antes era
   opcional, y sin eso una hoja de 26 meses se sumaba entera en un solo número). Ya estaba
   confirmado con `cobros_historico.csv` (26 meses). Se volvió a correr `pedir_mapeo_a_claude`
   contra `presupuestos_marzo2026.csv` (un solo mes, 57 filas) tras liberarse el crédito de
   API frenado desde el 2026-07-30: el modelo devolvió `columna_periodo=0` correctamente esta
   vez (orientación `transaccional` bien detectada). La hipótesis de "un solo mes = sin
   columna_periodo" **no se reprodujo** — no hizo falta tocar el `SYSTEM_PROMPT`. Queda como
   nota que el fallo anterior fue no determinístico (variación entre corridas del modelo, sin
   cambio de código de por medio), no un bug de instrucción.
2. **La verificación end-to-end final de la Fase I — diferida** (2026-07-31 → retomar
   mañana): correr archivos reales juntos por la UI de `probar_manual.py` y confirmar que
   ninguna sección se rompió, incluyendo el catálogo recién ampliado. Se decidió sumar
   documentos distintos/adicionales a los 4 originales (Excel + los 2 CSV + la foto) para
   ampliar la cobertura de la verificación, no repetir exactamente la misma corrida. No se
   automatizó porque `probar_manual.py` necesita las respuestas de la Guía de Diagnóstico
   como input (juicio de negocio, no algo que el agente deba inventar) además de la carga
   real de archivos por browser — requiere una pasada manual de Felipe.

### Hallazgos confirmados con datos reales, sin arreglar todavía

- **6 conceptos de una tabla de recall no tienen variable propia** (pacientes activos en
  cartera, inactivos +12 meses, reseñas pedidas, llamados salientes, turnos cancelados, tasa
  de ausentismo). El más urgente es `turnos_cancelados`: confirmado con una corrida real que,
  sin esa variable, el extractor mapea las cancelaciones directo a `no_shows`, contaminando
  KPI 4. Y sin `pacientes_activos_cartera`, `pacientes_vuelven_control` acepta un valor con
  el denominador equivocado (confirmado: confianza alta, 0.85-0.9, no la baja que debería
  tener por la ambigüedad). Aditivo a `schema.py`, no requiere cambio de prompt.
- **`costo_hora_sillon` está mapeada de la columna equivocada** — confirmado, no hipótesis:
  el valor de un mes real coincide exactamente con "Costos operativos" de otra hoja (un total
  mensual, no una tarifa por hora). No existe hoy una variable para "costo operativo mensual
  total", así que el extractor fuerza el mapeo a la más parecida. Necesita una variable nueva
  + ajuste de prompt.
- **`segunda_lectura` nunca alcanza a variables de foto o PDF**: siempre intenta releer el
  grid con `excel_parser.leer_hojas_crudas`, que para una imagen lanza y se descarta en
  silencio — justo las variables que más lo necesitarían (el prompt de `vision_parser` pide
  confianzas de 0.3-0.5 para manuscritos). Requiere un camino de API nuevo (reenviar la
  imagen), no un ajuste.
- **El ledger guarda período (mes), no día**: un `dias_hasta_respuesta` de un CSV real (1 a
  12 días) se pierde en la agregación mensual. Cambiar la resolución toca `ledger.py` + las
  17 métricas de `metricas_paciente.py` (todas comparan con `_diferencia_meses`).
- **`impacto_por_kpi` está plano en 1.0** (`pipeline.py`) — la dimensión "cuánto mueve el
  negocio" no aporta nada al ranking de oportunidades todavía. Y 5 intervenciones del
  catálogo con `kpi_objetivo=None` son estructuralmente inalcanzables (`mapear_oportunidades`
  sólo matchea por `kpi_objetivo`, nunca por `variable_objetivo`).

### Pendientes de antes, siguen sin resolver

- Conectar `cargar_variables_de_supabase` / `guardar_variables_en_supabase` con la tabla
  `kpi_snapshots` real — no hay Supabase conectado todavía.
- KPIs `sin_benchmark` (7, 10, 19) no entran al ranking numérico de `priorizacion.py` (no
  tienen gap contra el cual medir) — ver `TODO` en `priorizacion.py`.
- Si aparece una encuesta/informe de FOA, CORA, COMP o una muestra de 5-10 clínicas de Mar
  del Plata con datos reales de gestión, reemplazar los proxies internacionales en
  `benchmarks.py` y subir `confiabilidad` (ver Recomendaciones en
  `referencias/benchmarks_research_AR.md`).
- **Validación real del Diagnostic Engine (§24 del Documento Maestro)**: hoy sólo hay casos
  sintéticos (`evals/casos_diagnostico.py`). Falta el circuito real — casos anonimizados de
  clínicas reales, diagnóstico de un experto humano, comparación, y ajuste de
  reglas/benchmarks/prompt según esa comparación.
- **"Reputación"** (pedido de reseña) sigue aproximado con KPI 10 en vez de tener variable
  propia.
- No hay `requirements.txt` en el repo — las dependencias reales están instaladas en el
  `venv/` local (`anthropic`, `pandas`, `openpyxl`, `xlrd`, `rapidfuzz`, `streamlit`,
  `python-dotenv`, entre otras). Si se agrega uno, congelar las versiones del `venv` actual.
