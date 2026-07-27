# Próximos pasos — probar el parser en vivo (uploads reales)

Objetivo: subir un archivo/foto real y ver un output real (KPIs calculados,
preguntas del wizard, conflictos, interpretación), sin necesitar todavía
FastAPI, frontend ni Supabase.

Contexto (2026-07-27): revisé el board de Miro "KPIs + Asistente IA —
Clínicas Dentales (Agencia IA)" y audité el código real en `parser/`. Este
doc queda actualizado con dos objetivos que no estaban antes: poner la
carpeta bajo control de versión (hoy no hay `.git`, todo el trabajo vive
solo en disco) y, al final, sincronizar el Miro con la capa de benchmarks +
interpretación que ya existe en código pero el board todavía no refleja
("Sección 7").

## 0. Control de versión (hacer antes que nada)

Esta carpeta no está bajo git — dos planes ya ejecutados
(`plan_maestro_benchmarks_interpretacion.md`, `plan_resolucion_conflictos.md`)
y el motor de priorización nuevo viven solo en el filesystem, sin historial
ni forma de revertir un cambio malo.

1. `git init` en `agencia_ia_dental_dashboard/`.
2. Primer commit con el estado actual (parser completo, docs, docx de
   diagnóstico) antes de tocar nada más.

## 1. Bloqueadores de entorno (antes de tocar código)

1. **Python.** Esta máquina solo tiene 3.9 instalado, pero el código ya usa
   sintaxis 3.10+ (`X | None`). No corre tal cual. Instalar Python 3.10+
   (ej. `brew install python@3.12`, o pyenv) y armar un venv con esa
   versión antes de poder ejecutar nada sin parchear.
2. **Dependencias** (dentro del venv nuevo): `pip install pandas anthropic`.
3. **API key.** Exportar `ANTHROPIC_API_KEY` en el shell (o un `.env` +
   `python-dotenv`, nunca hardcodeada en el código). Sin esto,
   `excel_parser.py`, `vision_parser.py` e `interpretacion.interpretar_kpi`
   no pueden llamar a Claude.
4. **Revisar el placeholder de modelo.** `MODEL = "claude-sonnet-4-6"` en
   `extractors/excel_parser.py`, `extractors/vision_parser.py` e
   `interpretacion.py` no es un model id real — hay que reemplazarlo por
   uno vigente antes de probar (`claude-sonnet-5`) o la primera llamada
   real va a fallar.

## 2. Armar un runner mínimo (no hace falta FastAPI todavía)

Un script chico, ej. `parser/probar_manual.py`, que:
- reciba paths de archivos por argumento,
- llame a `pipeline.procesar_migracion(archivos)`,
- imprima `kpis_calculados`, `preguntas_wizard`, `conflictos_pendientes` y
  `variables_a_confirmar` de forma legible.

Esto alcanza para ver un output real sin construir wizard, frontend ni
conexión a Supabase todavía.

## 3. Conseguir archivos reales de prueba

- Un Excel/CSV real (o ficticio pero realista, con nombres de columnas
  ambiguos como los usaría la clínica) para probar que Claude mapea bien
  contra el vocabulario de `schema.py`.
- Una foto de una planilla o cuaderno (real o simulada) para probar
  `vision_parser.py` — esto nunca se corrió contra la API real todavía.
- Idealmente, un caso con conflicto real: la misma variable con valores
  distintos en dos archivos, para ver `conflictos_pendientes` en la
  práctica (no solo en los tests sintéticos).

## 4. Correr y ajustar

- Correr el runner con los archivos de prueba y revisar el mapeo que hace
  Claude vs. lo esperado.
- Ajustar el `SYSTEM_PROMPT` de `excel_parser.py`/`vision_parser.py` si el
  mapeo sale mal — es la primera ejecución contra la API real, es
  esperable tener que iterar.
- Probar el flujo completo: migración → `preguntas_wizard` → completar a
  mano lo que falte → `evaluar_cobertura` → `calcular_gap` →
  `interpretar_kpi` con cliente real, para ver una interpretación de
  punta a punta.

## 5. Testear benchmarks + interpretación con datos reales

- Con KPIs ya calculados, pasar 2-3 por `interpretar_kpi(..., client=cliente_real)`
  para ver la salida real del asistente — hasta ahora solo se probó el
  payload que se le manda (`client=None`), nunca la respuesta del modelo.
- Confirmar que el criterio de aceptación "mismo valor, contexto
  cualitativo opuesto → interpretación distinta" se sostiene en la salida
  real, no solo en la construcción del contexto (`construir_contexto_cualitativo`).

## 6. Opcional pero recomendable

- Guardar en `parser/referencias/` 1-2 archivos de prueba anonimizados que
  hayan funcionado bien, como fixture reproducible para el futuro.
- Anotar en `parser/README.md` cualquier ajuste al `SYSTEM_PROMPT` que
  haga falta después de ver mapeos reales, y actualizar la sección
  "Pendiente" a medida que estos puntos se resuelvan.

## 7. Sincronizar el Miro

Una vez validado el comportamiento real (pasos 4-5), actualizar el board
"KPIs + Asistente IA — Clínicas Dentales (Agencia IA)" con una Sección 7
que documente la capa de benchmarks + interpretación (`benchmarks.py`,
`aranceles_com.py`, `interpretacion.py`, `priorizacion.py`) — hoy existe en
código pero no en el diagrama de arquitectura, así que diseño y build
están divergiendo.
