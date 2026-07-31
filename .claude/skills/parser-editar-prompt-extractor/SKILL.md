---
name: parser-editar-prompt-extractor
description: Ajustar el SYSTEM_PROMPT de excel_parser.py o vision_parser.py, o exponer una variable nueva al modelo extractor. Usar cuando el mapeo de columnas sale mal contra un archivo real, cuando se agrega una variable que se extrae de Excel/foto, o cuando hay que sumar una unidad de origen nueva.
---

# Editar un SYSTEM_PROMPT de extractor

Los extractores usan a Claude como mapeador de columnas, NO como calculadora. El prompt tiene
reglas tácitas frágiles — romperlas reintroduce bugs ya corregidos.

## Reglas que NO se negocian

- **El JSON del prompt se deriva de `schema.py`, nunca se hardcodea**: `_VARIABLES_JSON`,
  `_KPIS_PORCENTUALES_JSON`, `_TIPOS_EVENTO_JSON`, unidades. Si agregás una variable, ya
  aparece sola en el prompt si la declaraste bien en el schema — no la copies a mano.
- **`excel_parser` filtra `VARIABLE_TYPES` por `list` y `ledger`**: esas no se mapean
  columna-a-columna (`VARIABLES_EXCEL`). El `ledger` se declara en un bloque aparte del prompt,
  no como una entrada de "mapeo". `vision_parser` además NO ofrece `ledger` (una foto no puede
  producir un dict de listas).
- **El modelo declara, el código calcula**: el modelo devuelve índices de columna, `unidad_origen`
  y agregación. Toda conversión numérica la hace Python vía `FACTORES_CONVERSION`. NUNCA pedirle
  al modelo "convertí vos el valor a minutos" — el contrato no lo transporta y falla en silencio.
- **Si agregás una unidad de origen nueva**, tenés que sumar el factor a `FACTORES_CONVERSION`
  (ej. `("horas", "minutos"): 60`), o la conversión no existe.
- **`thinking` siempre explícito**: `thinking={"type": "disabled"}` en las llamadas de extractor.
  Omitirlo corre adaptativo y se come el presupuesto de `max_tokens` sin dejar texto (ver
  `claude_utils.extraer_texto`).
- **Leer la respuesta con `claude_utils.extraer_texto`** (salta ThinkingBlocks y detecta truncado),
  no `respuesta.content[0].text`.
- **`max_tokens` actuales**: 8000 (Excel), 2000 (foto/PDF). Si un archivo real trunca, subirlo
  acá, no parchear el punto de uso.

## Al iterar contra un archivo real

1. Correr `probar_manual.py` (Streamlit) o `evals/runner.py` con el archivo — necesita
   `ANTHROPIC_API_KEY`.
2. Comparar el mapeo contra lo esperado. Ajustar la instrucción del prompt, no el código de
   conversión (salvo unidad nueva).
3. Anotar el ajuste en `parser/README.md` (sección de la fase correspondiente) — el prompt es
   parte del diseño, no un detalle.

## Trampas conocidas

- Una hoja transaccional necesita `columna_periodo` cuando hay columna de fecha; sin eso una
  hoja de N meses se suma entera en un número (hallazgo I6).
- Un ítem mal formado del modelo no debe tirar abajo el lote entero — se saltea con `continue`.
- El strip de fences ```` ```json ```` se repite en varias funciones; mantenelo consistente.
