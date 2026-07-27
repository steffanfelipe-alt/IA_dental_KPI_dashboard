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
