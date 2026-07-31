---
name: parser-editar-benchmark
description: Agregar o editar un benchmark argentino en benchmarks.py, o actualizar el arancel de referencia en aranceles_com.py. Usar cuando el Círculo Odontológico publique un arancel nuevo, cuando aparezca un dato argentino real que reemplace un proxy, o cuando haya que cargar un benchmark para un KPI que hoy no lo tiene.
---

# Editar un benchmark

De los 20 KPIs, 13 se comparan contra un benchmark; los otros 7 son financieros/internos
(dependen 100% del historial propio). El research (`referencias/benchmarks_research_AR.md`) es la
fuente de los valores. La regla de oro: **un rango falso es peor que no tener benchmark**.

## Campos del benchmark

- **`mejor_es`**: `"mayor"` o `"menor"`. Define `favorable` en el `Gap` — para no-show estar
  arriba es malo, para aceptación estar arriba es bueno. Sin esto, `direccion` sola no alcanza.
- **`confiabilidad`**: 4 niveles, graduados de más a menos firme (oficial → consultora_ar →
  proxy_internacional → sin_benchmark). Tiene que coordinar con el prompt de interpretación, que
  le pide a Claude ser más o menos categórico según la firmeza. El factor de priorización también
  lo usa (oficial 1.0, consultora_ar 0.85, proxy_internacional 0.6, sin_benchmark 0.4).
- **`es_multiplo_arancel`**: `True` para valores que se guardan como múltiplo de "consulta" (ej.
  ticket promedio, KPI 6) en vez de un monto fijo en ARS — así no se desactualizan por inflación.
  `calcular_gap` los resuelve contra `aranceles_com.ARANCEL_COM["consulta"]` en cada llamada.

## Cuándo dejar `sin_benchmark` (rango bajo `None`)

- No hay proxy confiable (KPIs 7, 10, 19 hoy).
- La conversión a un número exigiría inventar un tipo de cambio o tratar una estimación no
  auditada como cifra dura (KPIs 12, 15). En estos, la `nota` igual llega al asistente como
  orientación, pero sin rango numérico. **Nunca inventes el rango para "completar".**

## Actualizar el arancel (tarea recurrente)

El Círculo Odontológico de Mar del Plata publica el arancel varias veces al año. Actualizar el
único número en `aranceles_com.ARANCEL_COM["consulta"]` revaloriza solos todos los benchmarks
`es_multiplo_arancel`. No hay que tocar `benchmarks.py` para eso.

## Reemplazar un proxy por dato real

Si aparece una encuesta/informe de FOA, CORA, COMP o una muestra de clínicas de Mar del Plata:
reemplazar el rango, subir `confiabilidad`, y anotar la fuente en
`referencias/benchmarks_research_AR.md`.

## Tests

Invocar `parser-test-sin-pytest`. Correr `python3 test_benchmarks.py`.
