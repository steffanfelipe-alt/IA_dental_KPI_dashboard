---
name: parser-nueva-intervencion-catalogo
description: Agregar una intervención al catálogo tecnológico de Agencia IA (catalogo_tecnologico.py). Usar cuando haya un servicio/proceso nuevo que el sistema deba poder recomendar frente a un diagnóstico. El sistema NUNCA inventa soluciones — solo recomienda del catálogo.
---

# Agregar una intervención al catálogo

`catalogo_tecnologico.py` mapea cada diagnóstico a una intervención REAL del catálogo de Agencia
IA (§13 del Documento Maestro: nunca dejar que Claude invente una solución). Hay ~35, indexadas
por etapa del funnel.

## Campos de la dataclass `Intervencion`

**Obligatorios**: `id`, `etapa`, `nombre`, `tipo`, `metrica_objetivo`.

- **`etapa`**: una de `ETAPAS` (Captación → Conversión → Confirmación → Consulta → Post-consulta
  → Fidelización → Referidos). `diagnosticar()` dice en qué KPI está el cuello y la etapa da las
  candidatas sin traducción.
- **`tipo`**: `proceso` | `automatizacion` | `ia`. Importa: define `periodo_evaluacion_semanas`
  automáticamente en `__post_init__` vía `SEMANAS_EVALUACION_POR_TIPO` (proceso/automatizacion/ia
  → 4/8/12). NO lo setees a mano salvo que quieras override.
- **`metrica_objetivo`**: qué mueve. Tiene que existir como KPI o variable en `schema.py` (ver
  abajo).

**Opcionales relevantes**:

- **`requiere_integracion`** (bool): setealo EXPLÍCITO. Antes se infería por keyword-match sobre
  la descripción ("API"/"sistema") y penalizaba injustamente (Fase I3) — un chatbot quedaba
  último por su redacción. El campo explícito reemplaza esa heurística.
- **`kpi_objetivo`** / **`kpis_secundarios`** / **`variable_objetivo`** / **`metrica_paciente`**:
  enlace contra `schema.py`. Una intervención puede atacar más de un KPI (`kpis_secundarios`) —
  un agente de agendamiento 24/7 resuelve agendamiento Y tiempo de primera respuesta.
- **`como_funciona`** / **`beneficio`**: texto para el informe.

## Verificar antes de dar por mapeada

`mapear_oportunidades` matchea por `kpi_objetivo` (y no siempre por `variable_objetivo`). Una
intervención con `kpi_objetivo=None` es estructuralmente inalcanzable hoy. Confirmá que la
`metrica_objetivo` tiene un KPI que la mida; si no existe, primero invocá `parser-nueva-variable`
para crear la variable/KPI que falta (ej. "reputación"/pedido de reseña sigue sin variable propia,
aproximado con KPI 10).

## Tests

Invocar `parser-test-sin-pytest`. Correr `python3 test_catalogo_tecnologico.py` y `python3
test_priorizacion_extendida.py`.
