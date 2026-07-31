# Guía de Gentle AI en la terminal

Cómo manejarte desde el prompt de Claude Code para usar todo el sistema de
**subagentes** y **Spec-Driven Development (SDD)** de Gentle AI en este proyecto.

---

## 0. Modelo mental (leé esto primero)

- **La "terminal" es el prompt de Claude Code**, no un binario aparte. En esta
  máquina NO hay un CLI `gentle-ai` ni `gga` en el PATH (verificado). Todo se
  maneja tipeando en el prompt: comandos slash (`/sdd-...`) o lenguaje natural.
- **Vos dirigís, yo orquesto, los subagentes ejecutan.** Vos nunca lanzás un
  subagente vos mismo — le pedís algo al asistente (yo), y yo decido si lo hago
  inline o delego en uno o más subagentes con contexto propio.
- **Cada subagente arranca con contexto en blanco.** Lee su parte, hace su
  trabajo, y me devuelve un resumen. Eso es lo que mantiene tu conversación
  principal liviana (es exactamente lo que se hizo para generar el `AGENTS.md`:
  un subagente por módulo).
- **Backend de artefactos: Engram** (memoria persistente entre sesiones) es el
  default de tu setup. Con Engram, SDD NO usa ningún CLI externo — el estado
  vive en memoria y se recupera con búsqueda. (El otro backend, `openspec`,
  guarda archivos en `openspec/` y sí usa un dispatcher; no es tu caso salvo
  que lo pidas.)

---

## 1. Los tres tipos de trabajo con subagentes

| Tipo | Cuándo | Cómo lo disparás |
|---|---|---|
| **Delegación directa** | Explorar/mapear 4+ archivos, escribir 2+ archivos no triviales, research amplio | Lenguaje natural: "usá subagentes para…", "mapeá X delegando" |
| **Spec-Driven Development (SDD)** | Cambios sustanciales que conviene planificar antes de tocar código | `/sdd-new`, `/sdd-ff`, `/sdd-continue`, etc. |
| **Review adversarial (Judgment Day)** | Revisar un cambio con dos jueces ciegos antes de mergear | "juzgá esto", "dual review", `judgment-day` |

No todo necesita SDD. Un fix de un archivo entendido se hace directo. SDD es la
**capa de planificación** para lo grande.

---

## 2. Delegación directa (subagentes sin SDD)

Es lo más liviano. Lo pedís en lenguaje natural y yo elijo la topología mínima:

```
"Analizá el módulo de extractores delegando en un subagente y resumime
 las convenciones."

"Necesito entender cómo fluye un conflicto por el pipeline — mapealo con
 subagentes, uno por capa, y traeme un resumen."
```

Reglas que aplico solo (no las tenés que recordar):
- Leer 1–3 archivos para decidir → lo hago inline.
- Entender algo que toca 4+ archivos → delego UN subagente de exploración.
- Escribir 2+ archivos no triviales → delego UN subagente escritor.
- Varios subagentes en paralelo cuando las tareas son independientes (como el
  análisis módulo-por-módulo).

**Vos no tenés que pedir "lanzá 6 subagentes"** — alcanza con describir el
resultado que querés y decir que use subagentes; yo reparto.

---

## 3. Spec-Driven Development (SDD)

SDD estructura un cambio grande en fases antes de escribir código. La cadena:

```
proposal → specs → tasks → apply → verify → archive
             ↑
           design
```

### 3.1 Antes de nada: el Preflight (te lo pregunto una vez por sesión)

La primera vez que arrancás SDD en una sesión, te hago **una** pregunta agrupada
con 4 decisiones. Elegís y queda cacheado para toda la sesión:

| Decisión | Opciones | Qué significa |
|---|---|---|
| **Ritmo** | Interactivo / Automático | Interactivo: te resumo y pregunto tras cada fase. Automático: corre de corrido, yo valido entre fases. |
| **Artefactos** | OpenSpec / Engram / Ambos | Dónde se guardan proposal/spec/design/tasks. Tu default: **Engram**. |
| **PRs** | Preguntarme / Un solo PR / Auto | Qué hacer si el cambio es grande (partir en PRs encadenados o no). |
| **Presupuesto de review** | 400 / 800 / Otro | Cuántas líneas cambiadas antes de frenar y pedirte OK por la carga de review. |

Si no inicializaste SDD en el proyecto todavía, primero corro `/sdd-init`
(detecta stack, capacidad de tests, TDD estricto). **Este proyecto todavía NO
tiene SDD inicializado** — la primera vez que uses SDD, va a arrancar por ahí.

### 3.2 Comandos slash (los que tipeás)

**Autocompletables:**

| Comando | Qué hace |
|---|---|
| `/sdd-init` | Inicializa SDD en el proyecto (stack, tests). Una vez por proyecto. |
| `/sdd-explore <tema>` | Investiga una idea. No escribe código. |
| `/sdd-status [cambio]` | Estado estructurado, solo lectura. "¿En qué fase estoy?" |
| `/sdd-apply [cambio]` | Implementa las tareas pendientes en lotes. |
| `/sdd-verify [cambio]` | Valida que lo implementado cumpla spec/tasks. |
| `/sdd-archive [cambio]` | Cierra un cambio ya verificado. |
| `/sdd-onboard` | Recorrido guiado de punta a punta sobre tu propio código. |

**Meta-comandos (no salen en autocomplete, los tipeás igual):**

| Comando | Qué hace |
|---|---|
| `/sdd-new <cambio>` | Exploración + propuesta. **El arranque normal de un cambio nuevo.** |
| `/sdd-continue [cambio]` | Corre la siguiente fase lista según dependencias. |
| `/sdd-ff <nombre>` | Fast-forward: proposal → specs → design → tasks de una. |

### 3.3 Una sesión típica

```
# Arrancar un cambio nuevo (te hago el preflight la primera vez)
/sdd-new agregar-variable-turnos-cancelados

# (revisás la propuesta) … seguir con la siguiente fase
/sdd-continue

# o saltear toda la planificación de una:
/sdd-ff agregar-variable-turnos-cancelados

# cuando spec+design+tasks están listos, implementar
/sdd-apply

# validar contra la spec
/sdd-verify

# cerrar
/sdd-archive

# en cualquier momento, ver dónde estás
/sdd-status
```

### 3.4 Qué hago yo por atrás (para que sepas qué esperar)

- Cada fase la corre un **subagente dedicado** con su propio contexto, que
  lee/escribe el artefacto en Engram (no te copio el texto entero al prompt).
- En modo **Automático**, valido el resultado de cada fase antes de lanzar la
  siguiente (contrato, que los archivos existan, que no haya deriva). Si una
  fase falla, la reintento UNA vez con feedback; si vuelve a fallar, freno y te
  aviso.
- Si `tasks` estima un cambio grande (>400 líneas), aplico tu decisión de PRs
  del preflight (partir en PRs encadenados, un solo PR, o preguntarte).

---

## 4. Review adversarial — Judgment Day

Para revisar un cambio con dureza antes de mergear. Reemplaza al review normal
(4R) para ese target — nunca corren los dos juntos.

### Cómo lo disparás

```
"juzgá este cambio"
"dual review de lo que cambié en pipeline.py"
"corré judgment day sobre el branch"
```

### Qué pasa

1. Congelo un **target inmutable** (el diff exacto a revisar).
2. Lanzo **dos jueces ciegos en paralelo** (`jd-judge-a`, `jd-judge-b`), mismos
   criterios, solo lectura. Espero a los dos.
3. **Solo se arregla lo que ambos jueces confirman como grave.** Si lo reporta
   uno solo → queda como sospecha, no se toca. Si se contradicen → escalo para
   que decidas vos.
4. Antes de aplicar el primer arreglo, te pregunto. El fix lo hace un actor
   acotado (`jd-fix-agent`), solo sobre los IDs confirmados.
5. Máximo **dos rondas** de fix + re-juicio. Después: verificación final y un
   veredicto único: `JUDGMENT: APPROVED ✅` o `JUDGMENT: ESCALATED ⚠️`.

### El review "normal" (4R) — sin pedir judgment day

Para tu diff local: `/code-review`. Corre reviewers por lente
(`review-risk` = seguridad, `review-readability` = legibilidad,
`review-reliability` = tests/robustez, `review-resilience` = fallbacks), con un
`review-refuter` que filtra hallazgos inferenciales. Solo bloquea lo grave
causado por el cambio.

> `/code-review ultra` (alias viejo: `/ultrareview`) lanza una revisión
> multi-agente en la nube del branch. Es disparada por vos y facturable; yo no
> puedo lanzarla sola.

---

## 5. Otras skills útiles del ecosistema (las invoco yo, o las pedís por nombre)

| Skill | Para qué |
|---|---|
| `branch-pr` | Crear PRs con checks issue-first. |
| `chained-pr` | Partir cambios >400 líneas en PRs encadenados. |
| `work-unit-commits` | Planificar commits como unidades revisables. |
| `comment-writer` | Comentarios de PR/review cálidos y directos. |
| `issue-creation` | Crear/triage de issues de GitHub desde evidencia. |
| `skill-creator` / `skill-improver` | Crear o auditar skills. |
| `cognitive-doc-design` | Escribir docs que bajan la carga cognitiva. |

Skills **propias de este proyecto** (viven en `.claude/skills/`, ver `AGENTS.md`):
`parser-nueva-variable`, `parser-editar-prompt-extractor`,
`parser-nuevo-cruce-dimensional`, `parser-nueva-metrica-paciente`,
`parser-nueva-intervencion-catalogo`, `parser-editar-benchmark`,
`parser-test-sin-pytest`. Las invoco automáticamente cuando la tarea matchea.

---

## 6. Chuleta rápida — qué tipear para qué

| Querés… | Tipeás |
|---|---|
| Que explore/entienda algo grande sin ensuciar el chat | "usá subagentes para mapear X" |
| Planificar un cambio grande desde cero | `/sdd-new <nombre>` |
| Saltar toda la planificación de una | `/sdd-ff <nombre>` |
| Seguir a la próxima fase | `/sdd-continue` |
| Ver en qué fase estás | `/sdd-status` |
| Implementar lo planificado | `/sdd-apply` |
| Validar contra la spec | `/sdd-verify` |
| Cerrar el cambio | `/sdd-archive` |
| Aprender SDD sobre tu propio código | `/sdd-onboard` |
| Revisión dura con dos jueces | "juzgá esto" / `judgment-day` |
| Review normal de tu diff | `/code-review` |

---

## 7. Estado real de tu setup (a hoy)

- ✅ **Engram activo** — memoria persistente entre sesiones (backend default de SDD).
- ✅ **Skills globales instaladas** — SDD, judgment-day, review, branch-pr, etc.
  (en `~/.claude/`, compartidas entre todos tus proyectos).
- ✅ **`.gga` + `AGENTS.md` + 7 skills del parser** — commiteados en este repo.
- ⚠️ **SDD NO inicializado en este proyecto** — no hay `openspec/` ni contexto
  `sdd-init`. La primera vez que uses SDD, arranca por `/sdd-init`.
- ⚠️ **No hay CLI `gentle-ai`/`gga` en el PATH** — todo se maneja desde el prompt
  de Claude Code. Con Engram como backend, no hace falta ningún binario externo.
