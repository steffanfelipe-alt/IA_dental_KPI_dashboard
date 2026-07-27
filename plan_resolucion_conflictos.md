# Plan: resolución de conflictos de variables migradas

## Contexto para Claude Code

Este plan aplica sobre el proyecto ya existente en `parser/` (schema.py,
coverage.py, pipeline.py, preguntas_wizard.py, extractors/). Leer esos
archivos antes de empezar — este plan asume y extiende su estructura
actual, no la reemplaza.

## Objetivo

Hoy, cuando el dueño de una clínica sube dos archivos que dan valores
distintos para la misma variable con confianza empatada, `pipeline._fundir`
elige el primero por orden de llegada, sin avisar a nadie. El comportamiento
correcto es: si hay empate real, no elegir por el usuario — mostrarle el
conflicto y que decida él cuál es el valor correcto (o cargue uno nuevo).

## Regla de negocio a implementar

Dado un conjunto de valores candidatos para una misma variable (de
distintos archivos migrados, o de una migración anterior + una nueva):

1. Si todos los candidatos tienen el mismo valor → no hay conflicto, se usa ese valor.
2. Si los valores difieren y la confianza más alta supera claramente al resto
   (diferencia ≥ `UMBRAL_EMPATE`, sugerido 0.1) → se resuelve automático,
   gana el de mayor confianza (comportamiento actual, se mantiene).
3. Si los valores difieren y las confianzas están empatadas o casi
   (diferencia < `UMBRAL_EMPATE`) → **conflicto real**. Esa variable:
   - NO se calcula ningún KPI que dependa de ella hasta que se resuelva.
   - Se agrega a una lista de conflictos pendientes de confirmación.
   - Nunca se le vuelve a preguntar al wizard como si fuera una variable
     nueva — se le muestra como "elegí cuál es correcto", no como
     pregunta abierta.
4. Si una variable ya tiene una resolución previa confirmada por el dueño
   (`fuente == "confirmado_por_dueno"`), esa gana siempre, sin importar qué
   diga cualquier archivo nuevo — salvo que el nuevo archivo también
   contradiga ese valor confirmado, en cuyo caso se abre un conflicto nuevo
   (fuera de alcance de este plan; dejar un `TODO` marcado en el código).

## Tareas

### 1. `coverage.py` — extender `VariableValue` y agregar `Conflicto`

- Agregar campo `archivo_origen: Optional[str] = None` a `VariableValue`
  (nombre de archivo o "wizard"/"sistema" si no viene de un archivo).
- Agregar nuevo dataclass:
  ```python
  @dataclass
  class Conflicto:
      variable: str
      candidatos: list[dict]  # [{"valor":, "archivo":, "fuente":, "confianza":}]
  ```
- Agregar campo `kpis_esperando_resolucion_conflicto: dict[int, list[str]]`
  a `CoverageResult` (kpi_id -> variables en conflicto que necesita).

### 2. Nuevo archivo `conflictos.py`

Crear módulo separado (no meterlo en `pipeline.py`, para poder testearlo
sin tocar el pipeline completo):

```python
UMBRAL_EMPATE = 0.1

def resolver_conflictos(
    fuentes: list[dict[str, VariableValue]],
) -> tuple[dict[str, VariableValue], list[Conflicto]]:
    """
    Agrupa todos los candidatos por variable a través de todas las fuentes.
    Devuelve (variables_resueltas, conflictos_pendientes).

    Una variable con fuente == "confirmado_por_dueno" en cualquiera de las
    fuentes gana siempre y no entra en la lógica de empate.
    """
```

Lógica interna:
- Agrupar candidatos por variable (incluir `archivo_origen` en cada uno).
- Si hay un candidato con `fuente == "confirmado_por_dueno"`, usar ese y
  descartar el resto para esa variable.
- Si no, comparar valores distintos: si el máximo de confianza supera al
  segundo por ≥ `UMBRAL_EMPATE`, resolver automático.
- Si no, crear un `Conflicto` y NO incluir esa variable en `variables_resueltas`.

### 3. `pipeline.py` — usar `resolver_conflictos` en vez de `_fundir`

- Reemplazar la llamada a `_fundir` en `procesar_migracion` por
  `resolver_conflictos`.
- Al extraer cada archivo (`extraer_archivo`), setear `archivo_origen` en
  cada `VariableValue` devuelta (usar `dataclasses.replace` con el nombre
  del archivo, ya que los extractores no lo hacen hoy).
- Agregar al payload de retorno:
  ```python
  "conflictos_pendientes": [
      {
          "variable": c.variable,
          "pregunta": f"Encontramos valores distintos para {c.variable}. ¿Cuál es correcto?",
          "opciones": c.candidatos,
          "permite_valor_manual": True,
      }
      for c in conflictos
  ]
  ```
- Las variables en conflicto se excluyen del dict que se pasa a
  `evaluar_cobertura` (pasan la lista de nombres en conflicto como
  parámetro nuevo, ver tarea 4).

### 4. `coverage.py` — `evaluar_cobertura` debe distinguir "en conflicto" de "nunca preguntado"

- Cambiar firma: `evaluar_cobertura(variables, variables_en_conflicto: set[str] = set())`.
- Al recorrer cada KPI: si alguna de sus variables requeridas está en
  `variables_en_conflicto`, no la mandes a `kpis_parciales` (que dispara
  preguntas nuevas del wizard) — mandala a
  `kpis_esperando_resolucion_conflicto`.
- `variables_para_wizard` no debe incluir variables en conflicto entre las
  preguntas nuevas (para eso está `conflictos_pendientes`, que es una UI
  distinta: elegir entre opciones, no completar un campo).

### 5. Endpoint nuevo: resolver un conflicto

```
POST /onboarding/{clinica_id}/resolver-conflicto
body: {"variable": "no_shows", "valor": 13, "fuente_elegida": "migracion_excel"}
      # o {"variable": "no_shows", "valor_manual": 15}  si el dueño ingresa un valor nuevo
```

Al recibir esto:
- Crear `VariableValue(valor=elegido, fuente="confirmado_por_dueno", confianza=1.0, archivo_origen=None)`.
- Guardarlo en `variables_previas` de esa clínica (la misma tabla/función
  que ya usa `pipeline.procesar_migracion` para `variables_previas`).
- Volver a correr `procesar_migracion` para esa clínica y devolver el
  estado actualizado (kpis recalculados, conflictos restantes).

### 6. Frontend (fuera del alcance de este backend, solo dejar la forma clara)

El wizard necesita una pantalla nueva, distinta a "completá este dato":
tarjeta de conflicto mostrando cada candidato con su archivo de origen
("Excel_turnos.xlsx dice 56", "Foto_cuaderno.jpg dice 60"), botones para
elegir uno, y un campo para ingresar un tercer valor si ninguno es correcto.

## Criterios de aceptación

- [ ] Dos archivos con el mismo valor para una variable → no genera conflicto.
- [ ] Dos archivos con valores distintos y confianzas 0.9 vs 0.5 → se
      resuelve automático (gana 0.9), sin conflicto.
- [ ] Dos archivos con valores distintos y confianzas 0.8 vs 0.75 (diferencia
      < 0.1) → genera un `Conflicto`, la variable no se calcula, ningún KPI
      que la use aparece como calculado ni como pregunta nueva del wizard.
- [ ] Resolver el conflicto vía el endpoint hace que, en la siguiente
      corrida, esa variable tenga `fuente == "confirmado_por_dueno"` y el
      KPI correspondiente se calcule.
- [ ] Si se sube un tercer archivo después de una resolución confirmada,
      ese archivo NO reabre el conflicto (la resolución del dueño gana
      siempre) — dejar comentario `TODO` para el caso de contradicción
      posterior a una confirmación.

## Tests a agregar

- `test_conflictos.py`:
  - Caso sin conflicto (valores iguales).
  - Caso resuelto automático (confianzas bien distintas).
  - Caso de conflicto real (confianzas empatadas, valores distintos).
  - Caso con `confirmado_por_dueno` presente — debe ganar siempre.
- Actualizar el test manual de `coverage.py` (el que se corrió en el chat
  con datos sintéticos) para incluir un escenario con conflicto y verificar
  que el KPI afectado no aparece ni en `kpis_calculados` ni generando una
  pregunta nueva del wizard, solo en `conflictos_pendientes`.
