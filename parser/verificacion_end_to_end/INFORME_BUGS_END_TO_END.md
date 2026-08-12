# Informe de verificación end-to-end — bugs y soluciones

**Fecha:** 2026-08-01
**Corrida:** `probar_manual.py` (Streamlit) contra la API real, manejado con Playwright headless.
**Documentos de prueba** (`parser/verificacion_end_to_end/documentos_prueba/`):
- `clinica_norte_metricas_abr-may2026.xlsx` — 3 hojas (Resumen mensual, Financiero, Operativo), Abril + Mayo 2026.
- `presupuestos_abril_mayo2026.csv` — 36 filas transaccionales (id_paciente, fecha, monto, estado, días_hasta_respuesta).
- `control_recall_junio2026.png` — foto simulada de una hoja de recall manuscrita, Junio 2026.

**Método:** una sola corrida (un dataset coherente) capturada con todos los contenedores expandibles abiertos + las 4 funciones de API disparadas una vez cada una (informe de clínica en Opus, panel completo, zoom a un KPI, proponer cruces). El material se auditó con 4 agentes en paralelo, cada uno cruzando los artefactos capturados contra los archivos fuente (ground truth) y el código.

> **Actualización (misma fecha, corrida de seguimiento):** se re-corrieron dos funciones que en la primera pasada habían quedado sin cerrar — **9b (proponer cruces)** con espera correcta por spinner, y **8c (zoom de KPI)** esta vez sobre **Tasa de no-show** (en la primera pasada el selectbox no había tomado y capturó "Consultas nuevas"). Resultados incorporados abajo. Ambas resultaron **confiables**.

> **Aviso de no-determinismo:** el `vision_parser` (lectura de foto) no es determinista. Este informe describe **esta** corrida; los valores exactos de la foto pueden variar entre ejecuciones, pero el patrón del bug principal es estructural.

---

## Veredicto de flujo de datos (leer primero)

- **Extracción desde Excel/CSV → KPIs: confiable.** Montos, conteos de embudo, tiempos, conversiones de unidad y elección de período vigente (Mayo) son **todos exactos**. Verificado a mano contra el xlsx y el csv.
- **Extracción desde la foto (`migracion_foto`): NO confiable en esta corrida.** El parser de visión desalineó filas y contaminó dos KPIs (ver Bug #1). Es el hallazgo más grave y fue **confirmado de forma independiente por 3 de los 4 agentes**.
- **Capa de interpretación (las 3 llamadas de API): confiable, no alucina.** Cada número que el asistente menciona traza a su propio payload; respeta los estados determinísticos y no inventa contexto. El riesgo NO está en el LLM: está upstream, en la extracción de la foto, que el LLM por diseño no puede detectar.
- **Las defensas del pipeline funcionaron** donde hay red de contención (reconciliación, cuarentena, baja-confianza) — salvo justo en el camino de la foto, que es el único sin segunda lectura (Bug #2).

---

## Tabla de bugs priorizados

| # | Bug | Área | Severidad | Estado |
|---|-----|------|-----------|--------|
| 1 | Visión desalinea filas de la foto (etiqueta↔valor corridos) | `vision_parser.py` | **Alta** | Reproducido (3× confirmado) |
| 2 | `segunda_lectura` inalcanzable para foto/PDF | `pipeline.py` | **Alta** | Reproducido |
| 3 | Trazabilidad 2a dice "sum de N registros" para un valor que es del último período | `excel_parser.py` / `trazabilidad.py` | Media | Reproducido |
| 4 | Faltan `turnos_cancelados` y `pacientes_activos_cartera` en el vocabulario | `schema.py` | Media | Causa raíz viva (síntoma atajado) |
| 5 | Payload de `interpretar_clinica` no incluye contexto cualitativo por-KPI | `interpretacion.py` | Media | Reproducido |
| 6 | Render: los `$` corrompen pasajes del informe 8a (MathJax) | `probar_manual.py` | Media | Reproducido |
| 7 | Cruces monto÷monto sin filtro de sentido de negocio (ratios >100% no interpretables) | `cruces.py` | Media | Esperado por diseño, mejorable |

Fuera de tabla (no son bugs): ledger LTV=0 es **esperado**, Bug 3 conocido (`costo_hora_sillon`) **no se reprodujo**, y 9b (cruces propuestos) quedó **cerrado en la corrida de seguimiento: funciona, con una redundancia menor** (ver abajo). Ver secciones de abajo.

---

## Detalle

### Bug #1 — El parser de visión desalineó las filas de la foto — **Alta**

Confirmado independientemente por 3 agentes contra la foto original.

El parser pareó cada etiqueta con el valor de la fila de al lado (desfasaje vertical). Valores extraídos vs. reales en `control_recall_junio2026.png`:

| Variable extraída | Valor que tomó | Qué era en la foto | Valor real |
|---|---|---|---|
| `pacientes_reactivados` | 70 | "Inactivos contactados este mes" | **9** |
| `pacientes_inactivos_contactados` | 460 | "Pacientes inactivos (+12 meses)" | 70 |
| `resenas_nuevas` | 35 | "Reseñas de Google **pedidas**" | **6** (obtenidas) |
| `pacientes_atendidos_periodo` | 1180 | "Pacientes activos en cartera" (un stock) | — (no es "atendidos") |

**Consecuencia:**
- **KPI 9 (Tasa de reactivación)** = 70/460 = **15,2%**, cae "dentro de rango 15-25%" y se marca **HEALTHY**. El valor real (9/70 = **12,9%**) queda **por debajo** del rango → el diagnóstico correcto sería PROBLEM, no una fortaleza.
- **KPI 10 (Reseñas/referidos)** usa 35 (pedidas) en vez de 6 (obtenidas) y 1180 (cartera) como denominador de "atendidos".
- **Agravante:** estas variables figuran en la sección 2a como **"sin traza registrada"** — no hay trazabilidad para auditarlas, así que el error pasa invisible.

**Por qué es tan grave:** contamina un veredicto "HEALTHY" con datos basura. La capa de API después declara "reactivación es una fortaleza" sobre un número inventado por el mis-mapeo — y ningún LLM puede detectarlo porque no ve la foto.

**Fix sugerido:**
1. Reforzar el `SYSTEM_PROMPT` de `parser/extractors/vision_parser.py` para el pareo fila↔valor (usar el skill `parser-editar-prompt-extractor`): pedir explícitamente que asocie cada valor a la etiqueta de SU MISMA fila, y que ante duda de alineación reporte confianza baja.
2. Agregar una validación cruzada de sentido en `validacion.py`/`reconciliacion.py`: `reactivados ≤ contactados ≤ inactivos`. Una relación rota es señal de desalineación.
3. Ver Bug #2 — una segunda lectura sobre la imagen habría atajado esto.

---

### Bug #2 — `segunda_lectura` es estructuralmente inalcanzable para foto/PDF — **Alta**

La última red de seguridad (releer con confianza baja) no cubre justamente la fuente más frágil: la visión.

**Causa (en código):** `pipeline.py:196` (aprox.) llama `excel_parser.leer_hojas_crudas(path)` para TODO archivo, incluso imágenes. Esa función solo maneja `.csv` y `pd.ExcelFile`; con un PNG lanza excepción → se atrapa con `grids_cache[path] = []` → `if not hojas: continue` (`pipeline.py:200-201`). Las variables de imagen se saltean sin segunda lectura y su confianza nunca sube.

**Fix sugerido:** en `pipeline._segunda_lectura_para_variables_dudosas` (~líneas 192-207), ramificar por fuente: para `migracion_foto`, re-invocar `vision_parser` sobre la imagen (relectura ciega) en vez de `leer_hojas_crudas`. Hoy `segunda_lectura.py` solo contempla grid de texto.

---

### Bug #3 — La trazabilidad dice "sum de N registros" para un valor que es del último período — **Media**

Los **valores de KPI son correctos** (tomar el último período es la elección correcta), pero la sección 2a — cuyo único propósito es auditar de dónde sale el número — **describe mal la agregación**.

**Evidencia:** 2a muestra `consultas_nuevas_mes: 102.0 ... sum de 2 registros`, pero 88 (Abril) + 102 (Mayo) = 190. El 102 es el valor de Mayo, no la suma. Mismo patrón en `monto_cobrado` (dice "sum de 2 registros" para 4.675.000, que es solo Mayo) y en la ruta CSV: `monto_presupuestos_emitidos: 8613698.0 ... sum de 36 registros` cuando 8.613.698 es solo Mayo (21 filas; el total de las 36 sería 14.118.251).

**Riesgo:** un auditor que confíe en la traza concluiría que se sumaron los meses. Compromete la auditabilidad, no los valores.

**Fix sugerido:** en `excel_parser.py:922` (aprox.), cuando hay serie por período, `n_registros` (y la etiqueta de agregación en `trazabilidad.py`) debe reflejar solo las filas del período vigente, o el texto decir "valor del último período (Mayo), no suma del rango".

---

### Bug #4 — Faltan `turnos_cancelados` y `pacientes_activos_cartera` en el vocabulario — **Media** (causa raíz viva, síntoma atajado)

Estos son dos de los bugs conocidos de Fase I. El **síntoma final está atajado**, pero la **causa raíz sigue viva**:

- **`turnos_cancelados` → `no_shows`:** el 19 ("Turnos cancelados") se mapeó a `no_shows`. La reconciliación lo detectó (27,1% calculado vs 21,43% declarado), lo mandó a cuarentena y derivó el valor correcto `no_shows = 15` (= 70 agendados − 55 asisten). **El KPI 4 final = 21,4% es correcto.** Pero el 19 todavía compite por `no_shows` desde el inicio porque no tiene variable propia.
- **`pacientes_activos_cartera`:** el 1180 cae en `pacientes_atendidos_periodo` (denominador equivocado del KPI 10). **Buena noticia:** el sistema lo degradó a **baja confianza** (sección 5) en vez de asertarlo con confianza alta — la variante peligrosa del bug conocido **no** se materializó.

**Fix sugerido:** agregar ambas variables a `schema.py` (`VARIABLE_TYPES` + `METRICAS`) y cablearlas en los prompts de extractor, usando el skill `parser-nueva-variable`. Así el 19 y el 1180 tienen destino propio y dejan de contaminar `no_shows` / `pacientes_atendidos_periodo`.

---

### Bug #5 — El payload de `interpretar_clinica` no incluye el contexto cualitativo por-KPI — **Media**

El informe 8a (el más completo, corre en Opus) sale **más pobre** que el panel 8b en la sección de causas.

**Evidencia:** en el payload de 8a, las hipótesis llegan con `causa_probable = "ver contexto cualitativo asociado a este KPI"` (referencia colgante) y apuntan a P1/P2/P5/P6/P7 — pero esos textos **no viajan en el payload**: `_payload_clinica` solo arma `contexto_general` (P44/45/46/51). El panel 8b sí los tiene, por eso puede nombrar las fallas concretas del proceso de confirmación y 8a no.

**El LLM se comportó bien:** no inventó el contenido de los P que no recibió (se calló, en vez de alucinar).

**Confirmado en la corrida de seguimiento:** el zoom de no-show (8c, `interpretar_kpi`) **SÍ** recibió el contexto cualitativo por-KPI en su payload (`contexto_cualitativo` con P1/P2/P5/P6/P7/P44/P45/P46/P51) y lo usó muy bien (nombró la confirmación manual de P2, el hueco no reemplazado de P5, el doble-booking de P7). Es decir: `interpretar_kpi` y `interpretar_panel` reciben el contexto por-KPI; el único que NO lo recibe es `interpretar_clinica` (8a). Eso acota el fix a un solo entry point.

**Fix sugerido:** en `interpretacion.py:554-564` (`_payload_clinica`, aprox.) agregar `contexto_cualitativo` por KPI, como ya hacen `interpretar_panel` (~línea 319) e `interpretar_kpi`, al menos para los KPIs con `problema`.

---

### Bug #6 — Los `$` corrompen pasajes del informe 8a en el render — **Media**

Dos pasajes del informe (hipótesis de throughput y sección 9 Paso 0) se vuelven un amasijo de caracteres itálicos matemáticos: Streamlit/MathJax interpreta los `$…$` de los montos como fórmulas LaTeX. El **texto subyacente y los números son correctos** — es solo display.

**Fix sugerido:** escapar `$` al renderizar el informe. El harness ya tiene un helper `_md()` para esto (se usa en otras secciones), pero no se aplica en `probar_manual.py:627` (aprox.), donde hace `st.markdown(resultado_informe["informe"])` sin escapar. Alternativa: formatear montos como "ARS 4.675.000".

---

### Bug #7 — Cruces monto÷monto sin filtro de sentido de negocio — **Media** (mejorable)

Los ~21 cruces determinísticos de la sección 9 son **dimensional y aritméticamente correctos** (verificado contra la fuente). Pero la capa monto÷monto genera TODOS los pares de montos en ARS sin filtro semántico — a diferencia de conteo÷conteo, que sí se restringe al embudo.

**Ejemplo problemático:** "Monto cobrado / Monto presupuestos aceptados = **194,7%**". Cruza dos poblaciones de dinero no comparables, de archivos distintos (cobrado del xlsx = flujo del mes; presupuestos aceptados del csv = valor facial de solo 8 de 36 filas). El >100% se lee como una "tasa de cobro rota", cuando la tasa de cobro real es 95,6% (KPI 13). Es ruido de baja interpretabilidad. (En cambio "Facturado − Cobrado = $215.000" = cuentas por cobrar, sí es útil.)

**Fix sugerido:** en `cruces.py:271-287` (aprox., `generar_cruces_algebraicos`), aplicar a monto÷monto un criterio de pertenencia análogo al del embudo: permitir solo pares de la misma familia (cobrado/facturado/presupuestado entre sí) o exigir mismo `archivo_origen`, en vez de todo-contra-todo.

---

## Lo que funcionó bien (no tocar)

- **Reconciliación + cuarentena:** atajaron el `no_shows`=19 mal mapeado y derivaron el 15 correcto. Defensa funcionando como se diseñó.
- **`costo_hora_sillon` (Bug 3 conocido) NO se reprodujo:** el total de "Costos operativos" (3.180.000/3.340.000) no se forzó a la tarifa por hora. No dejó rastro en ningún KPI ni cuarentena.
- **Las 3 salidas de API no alucinan:** informe de clínica (8a), panel (8b) y zoom de KPI (8c) — cada número traza a su payload, respetan los estados determinísticos (no suben un HEALTHY a PROBLEM ni viceversa), hedgean lo que no pueden confirmar y no inventan contexto de la clínica.
- **Zoom de no-show (8c, corrida de seguimiento): interpretación de alta calidad.** Fidelidad numérica impecable (21,4%, rango 8-15%, típico AR 25-30%, serie 24,6→21,4, 9 semanas, ponderación 50/50 — todo traza al payload). Además es accionable y correcta: detecta el matiz de que la clínica está mejor que el promedio argentino pero lejos de la meta, marca la tendencia de mejora como incipiente (hedge por 9 semanas), identifica la confirmación manual (P2) como el punto débil y hasta señala que el doble-booking (P7) contamina la métrica. `diagnostico: NULL` → no inventó un diagnóstico determinístico.
- **9b (proponer cruces con IA): funciona.** En la corrida de seguimiento (con espera correcta por spinner) el modelo propuso **un** cruce válido: "Monto facturado − Monto cobrado = $215.000" (cuentas por cobrar), con una explicación de negocio correcta. *Redundancia menor (severidad baja):* ese mismo cruce **ya existe** en la sección 9 determinística — no hay deduplicación entre lo propuesto por IA y lo que el motor ya calculó. Mejora opcional: en `cruces_propuestos.py`, filtrar propuestas cuya fórmula ya esté en `resultado["cruces"]`. Que proponga solo uno es consistente: la sección 9 ya cubre los pares obvios y `_validar_propuesta` descarta el resto.
- **Ledger LTV=0 es ESPERADO, no bug:** `ltv_real` (`metricas_paciente.py:127`) solo suma eventos `tipo_evento == "pago"`; un CSV de **presupuestos** genera eventos `presupuesto_emitido`/`presupuesto_aceptado`, nunca `pago` (un presupuesto es una cotización, no un cobro). El ledger SÍ se pobló — las métricas de ciclo de presupuesto (velocidad presupuesto→aceptación, mix de tratamientos, nuevos vs recurrentes) tienen datos. Solo la tile de cabecera "Pacientes con LTV registrado: 0" engaña aislada.
  - *Mejora opcional de UX:* agregar una tile "pacientes en el ledger" = `len(ledger)` para que 0-LTV no se lea como ledger vacío (`probar_manual.py:788-795`).

---

## Cerrado en la corrida de seguimiento

- **9b (cruces propuestos por IA): CERRADO — funciona.** Con espera correcta por spinner, el modelo propuso un cruce válido (cuentas por cobrar, $215.000). Único pendiente: redundancia con la sección 9 (ver "Lo que funcionó bien"). El punto lateral sigue vigente: `cruces_propuestos.py:230-235` degrada `json.loads` roto a `[]` en silencio — defensivo, pero indistinguible de "cero propuestas".
- **8c zoom de no-show: CERRADO — capturado y fiel.** En la corrida de seguimiento se seleccionó bien "Tasa de no-show" y la interpretación resultó impecable (ver "Lo que funcionó bien"). En la primera pasada el selectbox (un react-aria ComboBox) no había tomado y capturó "Consultas nuevas" — era una limitación de mi automatización, no del sistema.

## Notas menores

- **Serie no-show Abril:** el sistema calcula 24,6% (15/61) vs 23,9% declarado en la planilla. Es defendible — el cálculo del parser es más consistente que la tasa redondeada de la fuente; solo notar que la serie histórica no replica exactamente la columna del Excel.

- **`presupuestos_abril_mayo2026.csv` es un EXTRACTO PARCIAL, no el universo completo (verificado 2026-08-03).** El CSV trae 15 filas en Abril y 21 en Mayo, pero la clínica entregó 43 y 50 presupuestos respectivamente (hoja "Resumen mensual" → "Presup. entregados", con el total del XLSX internamente consistente: 43 × 268.000 = 11.524.000 y 50 × 271.500 = 13.575.000). Por eso el `monto_presupuestos_emitidos` del CSV (Mayo 8.613.698) discrepa ~37% del XLSX (13.575.000): **el correcto es el del XLSX**; el CSV subcuenta porque le faltan filas, no por filtro de estado (están pendiente/aceptado/rechazado). Esto NO es un bug del parser — la reconciliación detectó la discrepancia y frenó a preguntar, que es lo correcto. Al reproducir la corrida E2E con estos fixtures, elegir el candidato del XLSX en la sección 4.

---

## Orden de fixes sugerido

1. **Bug #1** (visión desalinea filas) — corrompe un veredicto HEALTHY en silencio. Máxima prioridad.
2. **Bug #2** (segunda lectura no cubre foto) — es la red que atajaría el #1.
3. **Bug #3** (trazabilidad "sum de N") — barato y restaura la auditabilidad.
4. **Bug #4** (variables faltantes en schema) — ataca la causa raíz de dos bugs conocidos.
5. **Bug #5** (contexto cualitativo en payload 8a) — mejora la calidad del informe principal.
6. **Bug #6** (render `$`) — cosmético pero deja párrafos ilegibles; fix de una línea.
7. **Bug #7** (cruces monto÷monto) — mejora de interpretabilidad, no de correctitud.

---

## Anexo — cómo se generó

- Captura: `Playwright` headless contra `http://localhost:8501`, script que sube los 3 archivos + respuestas de la Guía de Diagnóstico, procesa, abre todos los expanders y dispara las 4 funciones de API.
- Artefactos crudos (texto + screenshots de cada fase) quedaron en el directorio temporal del job, no en el repo.
- Análisis: 4 agentes en paralelo (extracción/KPIs, conflictos/cuarentena/bugs-conocidos, salidas de API, ledger/cruces/visión), cada uno cruzando artefactos contra archivos fuente y código.
