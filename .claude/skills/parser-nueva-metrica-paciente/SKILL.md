---
name: parser-nueva-metrica-paciente
description: Agregar una métrica longitudinal al ledger de pacientes (metricas_paciente.py). Usar cuando se quiera medir riesgo/fuga, valor/concentración, ciclo de vida o atribución por paciente — algo que las 16 fórmulas fijas de schema.py no pueden expresar.
---

# Agregar una métrica de paciente

`metricas_paciente.py` calcula métricas sobre `ledger_pacientes` (`{cliente_id: [eventos]}`)
que las 16 `KPIFormula` no pueden expresar (no-show recurrente, LTV real, concentración de
ingresos, retención por cohorte, etc.). Una métrica de paciente NO tiene `kpi_id` — nunca se
mezcla con los KPIs en el payload.

## Contrato implícito de una métrica

- **Firma**: `def nombre_metrica(ledger, ...umbrales)` — el ledger primero, luego umbrales con
  default explícito.
- **Iterar** `ledger.items()`.
- **Usar los helpers existentes**: `_eventos_de_tipo`, orden cronológico, `_diferencia_meses`
  — no reimplementar el filtrado de eventos.
- **Ignorar eventos de tipo ausente** en vez de romper — un `cliente_id` sin eventos de `pago`
  simplemente no cuenta para LTV, no lanza.
- **Retorno**: `dict`, `list` u `Optional`, redondeado con `round` donde sea un monto/tasa.
- **Vocabulario de eventos**: `ledger.TIPOS_EVENTO`. Un tipo desconocido no rompe y no se cuenta.

## El paso que se olvida

**Registrar la métrica en `calcular_todas`** (el bundle que arma las 17 métricas). Si no la
agregás ahí, no aparece en el payload aunque la función exista. Actualizar también el conteo
"17" en docstrings/README si cambia.

## Resolución temporal (limitación conocida)

El ledger guarda período (mes), no día — un `dias_hasta_respuesta` de 1 a 12 días se pierde en
la agregación mensual. Si la métrica nueva necesita resolución diaria, es un cambio mayor que
toca `ledger.py` + todas las métricas que comparan con `_diferencia_meses`. No parchear una
sola métrica.

## Si necesitás un tipo de evento nuevo

Agregarlo a `ledger.TIPOS_EVENTO` y revisar qué métricas deberían consumirlo. Una fila puede
generar más de un evento (ej. un presupuesto aceptado es `presupuesto_emitido` Y
`presupuesto_aceptado`).

## Tests

Invocar `parser-test-sin-pytest`. Correr `python3 test_metricas_paciente.py` y `python3
test_ledger.py`.
