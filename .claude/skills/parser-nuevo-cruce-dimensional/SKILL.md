---
name: parser-nuevo-cruce-dimensional
description: Agregar una operación dimensional legal a cruces.py (OPERACIONES_LEGALES) o un tipo de cruce derivado nuevo. Usar cuando se quiera habilitar una métrica cruzada fuera de las 20 KPIFormula fijas (ej. una razón monto/conteo o conteo/horas nueva).
---

# Agregar un cruce dimensional

`cruces.py` genera métricas fuera de las 20 fórmulas fijas, en dos capas deterministas SIN API:
embudo (razones etapa-posterior/etapa-anterior) y álgebra de unidades (análisis dimensional).
Un `Cruce` no es un KPI: no tiene `kpi_id` ni entra a coverage/diagnóstico/priorización.

## `cruces.py` NO importa `anthropic`

Es deliberado — toda la capa determinista tiene que seguir siendo testeable sin red. La capa
que llama al modelo (Claude propone qué cruzar) vive aislada en `cruces_propuestos.py`. No
agregues imports de API acá.

## Pasos para una operación dimensional nueva

1. **`OPERACIONES_LEGALES`**: agregar la tupla `(unidad_a, operacion, unidad_b): unidad_resultado`.
   Es la única fuente de verdad del álgebra — el modelo declara `unidad_esperada` y el cruce se
   descarta si no coincide con `unidad_real`.
2. **Bucle en `generar_cruces_algebraicos`**: cablear la operación nueva si no cae en un bucle
   existente.
3. **Decidir la restricción semántica** — esto es lo que se olvida:
   - `monto ÷ conteo`: el conteo tiene que estar en `DENOMINADORES_VOLUMEN` (volumen de trabajo
     real: turnos, pacientes). Sin esto, `no_shows` podía terminar de denominador de un monto,
     sin sentido de negocio.
   - `conteo ÷ conteo`: NO va al álgebra — está confinado al embudo (`ETAPAS_EMBUDO`).
   - Restas: cuidar minuendo mayor / evitar espejados (`[i+1:]`).
4. **`formato.py`**: sumar la unidad resultado a `UNIDADES_ARS` / `UNIDADES_HORAS` para que se
   muestre bien. Si no, el número sale sin formato.
5. **Confianza**: nunca inventarla. `calcular_cruce` usa `min(confianza_a, confianza_b)`. Una
   propuesta de la capa 3 se topa además en `CONFIANZA_PROPUESTA = 0.6`.
6. **`_validar_propuesta`** (cruces_propuestos.py): verificar que acepte la operación nueva si
   querés que el modelo pueda proponerla.

## Tests

Invocar `parser-test-sin-pytest`. Correr `python3 test_cruces.py` y `python3
test_cruces_propuestos.py`.

## Trampa canónica

Olvidar el paso 4 (`formato.py`) o la exclusión de espejados en el paso 3 son los dos errores
más comunes — el cruce se genera pero se muestra mal, o se genera dos veces invertido.
