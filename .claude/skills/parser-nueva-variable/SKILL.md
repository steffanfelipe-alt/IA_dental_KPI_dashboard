---
name: parser-nueva-variable
description: Agregar o renombrar una variable del vocabulario del parser (schema.py) y cablearla en todos los lugares acoplados sin romper la cobertura por variable. Usar cuando se pida trackear un dato nuevo (ej. turnos_cancelados aparte de no_shows) o cuando un KPI necesite una variable que todavía no existe.
---

# Agregar una variable nueva al vocabulario

El vocabulario es la pieza central: wizard, extractores y las 16 fórmulas leen del MISMO
diccionario. Agregar una variable no es una línea — toca varios archivos acoplados y tiene
reglas sutiles. Este es el checklist en orden.

## 1. Declararla en `schema.py`

- **`VARIABLE_TYPES`**: agregar `"nombre_variable": "<tipo>"`. Tipos existentes: `int`,
  `float`, `dict` (desglose `{categoria: valor}`), `list`, `ledger`, `scalar_period`.
- **`METRICAS` (`MetricaInfo`)**: `nombre_humano`, `definicion`, `unidad_dato`, y —crítico—
  `no_confundir_con` y `sinonimos`. El hallazgo 1.3 documentó que sin `no_confundir_con` el
  extractor mapea dos variables parecidas al mismo valor. Si la variable es un `dict` cuya
  clave es un paciente, poné `entidad="paciente"`; si es un tratamiento u otra cosa, dejá
  `entidad=None` — sin esto el matching de personas fusionaría "Ortodoncia" con "Ortodoncia
  (plan completo)".

## 2. Decidir de dónde puede venir

- **`INTERNAL_VARIABLES`**: si la calcula el propio sistema (comparación antes/después), no
  la migración ni el wizard. Queda en `kpis_bloqueados_por_diseno` si falta.
- **`SOLO_MIGRACION_O_SISTEMA`**: si es un dato financiero que ningún dueño da de memoria
  (facturas, gastos) — nunca se pregunta en el wizard.
- Si no es ninguna, es una variable normal y va al wizard cuando falta.

## 3. Cablear los lugares que la consumen (solo si aplica)

- **`ETAPAS_EMBUDO`** (schema.py): si es una etapa del funnel, para que los cruces de
  conversión la usen.
- **`DENOMINADORES_VOLUMEN`** (schema.py): si puede ser denominador de un `monto ÷ conteo`
  (tiene que representar volumen de trabajo real: turnos, pacientes — nunca no_shows).
- **`IDENTIDADES`** en `validacion.py`: si participa en una identidad contable que hay que
  chequear.
- **`preguntas_wizard.py`**: el texto exacto de la pregunta que ve el dueño, salvo que sea
  interna o solo-migración.
- **Extractores**: si se extrae de Excel/foto, invocar el skill `parser-editar-prompt-extractor`
  — el SYSTEM_PROMPT se deriva del schema pero hay reglas propias.

## 4. Si además define/alimenta un KPI

Agregar o editar el `KPIFormula` en `KPI_FORMULAS` (`numerador`/`denominador`/`calcular`).
Si el KPI se compara contra benchmark, invocar `parser-editar-benchmark`.

## 5. Tests

Invocar `parser-test-sin-pytest`. Como mínimo: que la variable desbloquee el KPI esperado en
`test_coverage.py`, y que no rompa `test_pipeline.py`. Correr `python3 test_coverage.py` y
`python3 test_pipeline.py`.

## Trampas conocidas

- No renombrar una variable sin buscar todos sus usos (`grep` en `parser/`) — está referida
  por string en varios diccionarios.
- Una variable `dict` de pacientes SIN `entidad="paciente"` no pasa por matching (bug); una de
  tratamientos CON `entidad="paciente"` fusiona tratamientos como si fueran personas (bug).
