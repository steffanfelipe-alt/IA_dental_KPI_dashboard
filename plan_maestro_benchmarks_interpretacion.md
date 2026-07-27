# Plan maestro — Integrar benchmarks + interpretación IA al sistema

## 0. Contexto para Claude Code

Este plan integra una capa nueva (benchmarks argentinos + interpretación
del asistente) sobre el proyecto ya existente en `parser/`. **Leer primero**
todos los archivos actuales antes de tocar nada — este plan los extiende, no
los reemplaza:

- `schema.py` — 28 variables + 20 fórmulas de KPIs + `INTERNAL_VARIABLES` +
  `SOLO_MIGRACION_O_SISTEMA`.
- `coverage.py` — chequeo de cobertura por variable + generación de preguntas.
- `preguntas_wizard.py` — las 20 preguntas del wizard.
- `pipeline.py` — orquestador de migración.
- `extractors/excel_parser.py`, `extractors/vision_parser.py`.
- `benchmarks.py` — **NUEVO, hoy vacío** (estructura con valores en `None`).
- `interpretacion.py` — **NUEVO**, cruza gap + contexto cualitativo.

Fuente de los datos: `benchmarks_research_AR.md` (el documento de
investigación de Gemini) — se guarda en el repo como referencia.

Regla transversal de todo el plan: **nunca dar más precisión de la que el
dato permite.** 11 de 13 benchmarks son proxy internacional; el sistema
tiene que ser honesto sobre eso en cada pantalla y en cada respuesta del
asistente.

---

## 1. Ajuste estructural de `benchmarks.py` (hacer primero)

Antes de cargar valores, el dataclass `BenchmarkKPI` necesita dos campos
nuevos que el diseño original no tenía y que el research volvió obligatorios:

```python
@dataclass
class BenchmarkKPI:
    kpi_id: int
    rango_bajo: Optional[float]
    rango_alto: Optional[float]
    unidad: str
    mejor_es: str = "mayor"          # NUEVO: "mayor" | "menor" — dirección deseada
    es_multiplo_arancel: bool = False # NUEVO: si el valor se guarda como múltiplo de "consulta", no en ARS fijo
    fuente: str = ""
    fecha: str = ""
    confiabilidad: str = "sin_benchmark"  # "oficial" | "consultora_ar" | "proxy_internacional" | "sin_benchmark"
    nota: str = ""
```

**Por qué `mejor_es`:** hoy `calcular_gap()` reporta "por_debajo" / "por_encima"
sin saber si eso es bueno o malo. Para no-show, tiempo de respuesta, horas
admin y CAC, estar POR ENCIMA del rango es malo; para aceptación o recall,
estar por debajo es lo malo. Sin este campo, el asistente no puede saber si
un gap es una buena o mala noticia.

**Por qué `es_multiplo_arancel`:** los valores en pesos (ticket, producción
por hora) se desactualizan por inflación en semanas. La recomendación del
research es guardarlos como múltiplo del arancel "consulta" vigente, no como
número fijo en ARS. `calcular_gap()` para esos KPIs primero resuelve el ARS
real = múltiplo × valor_consulta_actual, y recién ahí compara.

`calcular_gap()` debe actualizarse para:
1. Usar `mejor_es` al etiquetar la dirección como favorable/desfavorable.
2. Si `es_multiplo_arancel`, resolver el valor contra el arancel vigente
   (traer `valor_consulta_actual` de una constante o tabla `aranceles_com`).

---

## 2. Cargar los 13 benchmarks

Mapeo research → schema (por nombre; NO coinciden los números). Cargar así:

| schema KPI | rango_bajo | rango_alto | unidad | mejor_es | confiabilidad | nota clave |
|---|---|---|---|---|---|---|
| 2 Tiempo 1ª respuesta | 0 | 5 | min | menor | proxy_internacional | ideal <2 min; >5 ≈ se pierde el lead |
| 3 Tasa de agendamiento | 35 | 50 | % | mayor | proxy_internacional | 35-50 con sistema; 15-25 sin sistema (poner en nota) |
| 4 Tasa de no-show | 8 | 15 | % | menor | consultora_ar | típico actual AR **25-30%**; meta sana <15, excelente <8. Si supera 30 → prioridad #1 |
| 5 Tasa de aceptación | 65 | 75 | % | mayor | proxy_internacional | 35-50 promedio, 65-75 sano; cae fuerte en alto monto |
| 6 Ticket promedio | (múltiplo) | — | consulta | mayor | oficial | `es_multiplo_arancel=True`; base consulta C.O.M. mar-2025 $29.795. Ver §3 |
| 7 Finalización | None | None | % | mayor | **sin_benchmark** | sin dato confiable → usar tendencia propia |
| 8 Recall / retención | 70 | 80 | % | mayor | proxy_internacional | <60 = fuga de base; retener cuesta 5-25× menos que captar |
| 9 Reactivación | 15 | 25 | % | mayor | proxy_internacional | umbral inactivo ~14 meses odont. general |
| 10 Reseñas / referidos | None | None | % | mayor | **sin_benchmark** | no hay % estándar → fijar meta propia (de X a Y en 90 días) |
| 12 Producción hora-sillón | (derivar) | — | ARS/h | mayor | proxy_internacional | USD 350-600/h proxy; calcular ARS = arancel × turnos/hora reales |
| 13 Tasa de cobro | 95 | 100 | % | mayor | proxy_internacional | ojo débitos de obras sociales; privado cobra ~100%, convenio pierde |
| 15 Horas admin/semana | None | None | hs/sem | menor | proxy_internacional | ~12 hs/persona liberables — orden de magnitud, NO cifra dura |
| 19 CAC nuevo vs. react | None | None | $/pac | menor | **sin_benchmark** | sin dato AR real; solo proxy España. Reactivar 5-7× más barato |

**Los 4 débiles (7, 10, 15, 19):** por decisión de diseño, 7/10/19 van como
`sin_benchmark` (mejor sin comparación que con una falsa). 15 queda como
proxy pero con `nota` fuerte de "orden de magnitud". Si más adelante aparece
un dato AR real (encuesta FOA/CORA, o muestra de 5-10 clínicas de MdP),
reemplazar y subir `confiabilidad`.

> **Decisión abierta:** dejé 7, 10 y 19 en `sin_benchmark`. Si preferís
> mostrarlos igual con el proxy débil marcado en rojo, es cambiar la
> confiabilidad — avisá antes de correr esto.

---

## 3. Ticket y producción como múltiplo de arancel (anti-inflación)

Crear una constante/tabla `aranceles_com.py`:

```python
# Arancel mínimo sugerido C.O.M. Mar del Plata — actualizar cuando el Círculo publique.
ARANCEL_COM = {
    "fecha": "2025-03",
    "consulta": 29795,   # unidad base de referencia
    # opcional, para el ticket por tipo de tratamiento:
    "endodoncia_unirradicular": 95653,   # ≈ 3.2 consultas
    "limpieza": 38328,                   # ≈ 1.3 consultas
    "corona_porcelana": 306238,          # ≈ 10.3 consultas
}
```

Para el ticket (KPI 6) el benchmark se guarda como múltiplo (ej. rango sano
del ticket promedio ponderado ≈ 1.5-3 consultas según mix). `calcular_gap()`
convierte a ARS con `ARANCEL_COM["consulta"]` vigente. Cuando el Círculo
publique nuevo arancel, se cambia UN número y todos los benchmarks en pesos
se revalorizan solos.

---

## 4. Ajustes de razonamiento del asistente (`interpretacion.py`)

### 4.1 La confiabilidad modula la firmeza
Agregar al `SYSTEM_PROMPT_BASE` la regla: el peso de un gap depende de
`confiabilidad_benchmark`. Contra `oficial` → afirmar con seguridad. Contra
`proxy_internacional` → presentar como orientación ("como referencia
internacional, no como dato argentino"). Contra `sin_benchmark` → no comparar,
analizar tendencia propia.

### 4.2 Sesgo comercial de las fuentes
Regla nueva en el system prompt: los proxies de KPIs digitales vienen de
software/agencias que venden la solución al problema que miden. Sus cifras
de "mejora" (ej. "reduce no-show 40%") son **dirección, no magnitud
garantizada**. El asistente NUNCA usa esos números como promesa en una
oferta comercial — solo para orientar dónde está el problema.

### 4.3 Estacionalidad de Mar del Plata
Conectar la respuesta P51 de la guía ("¿hay una época donde esto se
complica?") al interpretar KPI 4 (no-show) y KPI 12 (producción). Agregar
`"P51"` a `CONTEXTO_CUALITATIVO_POR_KPI[4]` y `[12]`. Regla: si el no-show
está alto Y estamos en temporada declarada por el dueño, distinguir pico
estacional de problema estructural en vez de dar el mismo diagnóstico.

### 4.4 Eje temporal: benchmark vs. historial propio (el ajuste grande)
Esto es lo que el research aporta y el diseño no tenía. El peso del
benchmark externo debe **bajar** a medida que la clínica acumula historial
propio en `kpi_snapshots`:

```python
def peso_benchmark_vs_historial(semanas_de_datos_propios: int) -> dict:
    if semanas_de_datos_propios < 4:
        return {"benchmark": 0.8, "historial": 0.2}   # recién arranca: se apoya en referencia externa (débil)
    elif semanas_de_datos_propios < 12:
        return {"benchmark": 0.5, "historial": 0.5}   # transición
    else:
        return {"benchmark": 0.2, "historial": 0.8}   # ya tiene su propia línea base: manda lo propio
```

`interpretar_kpi()` recibe `semanas_de_datos_propios` y `serie_historica` del
KPI, los mete en el payload, y el system prompt instruye al asistente a
ponderar según eso: al principio "comparado con la referencia (débil)..."; con
historial "tu propia tendencia: pasaste de X a Y, mejorando/empeorando".

---

## 5. Integración con el motor de priorización existente

El motor de priorización del Miro (score = gap × impacto, elige top-3
restricciones) sigue igual, con UN cambio: el score se multiplica por un
`factor_confiabilidad` para que un gap enorme contra un proxy débil no
rankee por encima de un gap mediano contra dato oficial.

```python
FACTOR_CONFIABILIDAD = {
    "oficial": 1.0,
    "consultora_ar": 0.85,
    "proxy_internacional": 0.6,
    "sin_benchmark": 0.4,   # se prioriza por tendencia propia + impacto, sin benchmark
}
# score_final = gap_normalizado * impacto * FACTOR_CONFIABILIDAD[confiabilidad]
```

Esto evita que el sistema le diga a un dueño "tu problema #1 es X" cuando
ese X salió de comparar contra un número que ni siquiera es argentino.

---

## 6. El documento de research dentro del sistema

- **Valores estructurados** → van a `benchmarks.py` (§2).
- **Caveats** (sesgo comercial, inflación, estacionalidad) → se vuelven
  reglas del system prompt (§4).
- **El documento entero** → se guarda en `parser/referencias/benchmarks_research_AR.md`
  como fuente citable. Si en el futuro se arma un asistente con base de
  conocimiento (RAG), este doc es uno de los primeros a indexar.

---

## 7. Orden de ejecución

1. Ajustar el dataclass `BenchmarkKPI` (§1) y `calcular_gap()`.
2. Crear `aranceles_com.py` (§3).
3. Cargar los 13 valores en `benchmarks.py` (§2).
4. Actualizar `interpretacion.py`: system prompt (4.1-4.3) + eje temporal (4.4)
   + `CONTEXTO_CUALITATIVO_POR_KPI` (agregar P51 a 4 y 12).
5. Meter `factor_confiabilidad` en el motor de priorización (§5).
6. Guardar el research en `parser/referencias/`.
7. Reempaquetar todo en `agencia_ia_dental_dashboard.zip`.
8. Actualizar el Miro: agregar "Sección 7 — Capa de interpretación y
   benchmarks" documentando este flujo.

---

## 8. Criterios de aceptación / tests

- [ ] `calcular_gap()` con `mejor_es="menor"` marca un no-show del 28% como
      desfavorable (no como "por encima = bueno").
- [ ] Un KPI `sin_benchmark` (7, 10, 19) nunca genera una comparación
      externa; el payload al asistente trae `direccion="sin_benchmark"` y
      la serie histórica propia.
- [ ] Ticket promedio se calcula contra `ARANCEL_COM["consulta"]`; cambiar
      ese único valor revaloriza el benchmark sin tocar nada más.
- [ ] Con `semanas_de_datos_propios=2` el payload pondera benchmark 0.8;
      con `=16`, pondera historial 0.8.
- [ ] En el motor de priorización, un gap contra `proxy_internacional`
      rankea por debajo de un gap equivalente contra `oficial`.
- [ ] El mismo valor de KPI con dos contextos cualitativos opuestos (P20
      "no hago seguimiento" vs. "sí hago seguimiento") produce
      interpretaciones distintas (test ya prototipado en el chat).

---

## 9. Trabajo relacionado pendiente (fuera de este plan)

- **`plan_resolucion_conflictos.md`** — resolución de conflictos de
  migración preguntando al dueño. Es independiente de esta capa; se puede
  ejecutar antes o después.
- **Wizard en el frontend (Next.js)** — consume `preguntas_wizard.py`.
- **Endpoint FastAPI** — expone `pipeline.procesar_migracion`.
- **Conectar a Supabase** — `cargar/guardar_variables` hoy son placeholders.
