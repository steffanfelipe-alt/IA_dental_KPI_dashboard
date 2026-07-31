# Guía de contribución y desarrollo seguro

Cómo trabajar en este repo para que la IA acelere sin meter deuda ni riesgo en
producción. Estas prácticas vienen de la Clase 3 del curso *"Desarrollo con IA:
de 0 a producción"* y están adaptadas a las convenciones reales de este proyecto
(motor de KPIs en Python, tests standalone sin pytest — ver `AGENTS.md`).

La premisa que ordena todo lo demás:

> **El desarrollador humano es el único responsable del código en producción.**
> La IA genera rápido, pero no entiende el negocio ni las ramificaciones de
> seguridad de lo que escribe. Genera; no valida. Validar es tu trabajo.

Todo lo que sigue existe para convertir esa responsabilidad en hábitos
automáticos, no en actos de disciplina que hay que recordar.

---

## 1. Testing: generar código con IA ≠ validar código

Que la IA produzca un cambio no dice nada sobre si el cambio es correcto. **Sin
tests, cada sugerencia de la IA es una apuesta**: funciona en tu cabeza, corre
una vez a mano, y nadie sabe qué rompió tres módulos más allá. El test es lo que
convierte "parece que anda" en "sé que anda, y sabré si deja de andar".

Reglas concretas:

- **No se testea todo — se blinda el valor de negocio y los edge cases.** El
  objetivo no es un número de cobertura; es que los escenarios que le importan a
  la clínica (un KPI mal calculado, un paciente fusionado por error, un dato
  rechazado que se filtra igual) tengan una red debajo. Un getter trivial no
  necesita test; la resolución de un conflicto de migración, sí.
- **El humano define qué escenario es realista y valida que lo sea.** La IA
  puede redactar la suite entera, pero no sabe que dos archivos migrados pueden
  dar valores distintos para la misma variable, ni que un ID de paciente puede
  venir vacío. Vos aportás el conocimiento del dominio; la IA, la mecánica de
  escribir los casos. Si no entendés por qué un test pasa, todavía no está listo.
- **Un cambio de comportamiento sin test que lo cubra no está terminado.**

### La convención de tests de este repo (no negociable)

Los tests son **standalone, sin pytest**. Cada módulo tiene su `parser/test_*.py`
que se corre solo:

```
python3 parser/test_pipeline.py
```

El patrón vive al final de cada archivo: junta todo lo que empieza con `test_`,
lo itera, imprime `OK  {nombre}` y el conteo total. Los tests son deterministas
y no tocan la red — los módulos que llaman a Claude reciben `client=None` o un
cliente falso que captura la última llamada.

- **No introducir pytest** ni sus fixtures: no está instalado y rompe la
  convención de los 363 tests existentes.
- Para escribir un test nuevo, seguí el skill `parser-test-sin-pytest`, que
  tiene la convención exacta (naming largo en español, runner, estructura).
- La métrica que se trackea es el **conteo de tests en verde**, reportado en
  cada actualización de `README.md`.

---

## 2. CI/CD: el guardián automático de producción

Dos siglas, una idea: que ninguna rotura llegue a producción sin que una máquina
la vea primero.

- **CI (Integración Continua):** cada push compila y corre los tests
  automáticamente. Si algo se rompe, te enterás al instante —no dos semanas
  después cuando ya no recordás qué tocaste—. El CI es el guardián que revisa
  todo lo que entra, sin cansarse ni saltearse casos por apuro.
- **CD (Entrega/Despliegue Continuo):** si el CI pasa, el cambio avanza a
  producción solo, sin pasos manuales que se olviden o se hagan mal.

La ganancia real no es la automatización por sí misma: es que **el criterio de
"esto está listo para producción" deja de vivir en la cabeza de una persona** y
pasa a ser un check reproducible que corre igual siempre.

---

## 3. Pull Requests y las reglas de oro

Este es el flujo cotidiano que adopta el proyecto. Aunque el historial viejo son
commits directos a `main`, de acá en adelante toda feature entra revisada y con
los checks en verde.

Las reglas de oro:

1. **Toda feature entra vía Pull Request a `main`.** Ninguna excepción por
   "es un cambio chico".
2. **Nunca push directo a `main`.** La rama queda protegida justamente para que
   esto no dependa de tu memoria (ver sección 5).
3. **Todo PR ejecuta automáticamente tres cosas:**
   - **lint** — que el formato sea consistente;
   - **validaciones** — chequeos de seguridad;
   - **tests** — que efectivamente funcione.
4. **Si algo falla → el PR se bloquea.** No se mergea rojo. El check en rojo no
   es una sugerencia.
5. **`main` siempre lista para producción.** Como nada entra sin pasar los
   checks, la rama principal es siempre desplegable.
6. **Conventional commits obligatorios.** Los mensajes van con prefijo
   (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`…). No es cosmético:
   es lo que le permite a **release-please** calcular la versión y armar las
   release notes solo (ver sección 7).

Por qué el PR y no el commit directo: el PR es el punto donde el cambio se hace
**visible y verificable antes de ser permanente**. Es donde corren los checks,
donde queda el registro de qué se cambió y por qué, y —cuando se active— donde la
revisión de seguridad con IA puede comentar antes de que el código sea `main`.

---

## 4. GitHub Actions: los workflows del repo

El repo ya trae workflows en `.github/workflows/`. Qué hace cada uno y por qué:

| Workflow | Cuándo corre | Qué hace |
|---|---|---|
| `ci.yml` | En cada PR | Lint + tests **offline** (deterministas, sin red). Es el gate de PR. |
| `tests-api.yml` | Manual (a mano) | Los tests que pegan a la **API de Claude** (`parser/evals/`). |
| release-please | Al mergear a `main` | Arma el Release PR y, al mergearlo, el tag y el release (sección 7). |

### Por qué los tests de API van separados del gate de PR

Los tests de `parser/evals/` corren el pipeline contra la **API real de
Anthropic**. Meterlos en cada PR sería un error por dos motivos:

1. **Costo.** Cada corrida consume créditos de la API. Un gate que se dispara en
   cada push a cada PR multiplica ese gasto sin agregar señal proporcional.
2. **No-determinismo del modelo.** La salida del LLM puede variar entre corridas;
   por eso `parser/evals/runner.py` compara con **tolerancia porcentual** y
   reporta precisión, no pass/fail. Un gate de PR necesita ser binario y
   reproducible: verde es verde siempre. Un check que a veces falla por el
   modelo, no por tu código, entrena al equipo a ignorar los rojos —lo peor que
   le puede pasar a un CI—.

Por eso el gate de PR corre **solo lo offline y determinista**, y los evals de
API se disparan a mano cuando querés medir precisión de extracción.

---

## 5. Protección de la rama `main`

`main` queda **protegida**: no se puede pushear directo, y un PR solo se mergea
con los checks requeridos en verde. Esto convierte las reglas de oro de la
sección 3 en algo que el repo **impone**, no que cada uno recuerda cumplir. La
disciplina que depende de la memoria falla el día que hay apuro; la que impone la
plataforma, no.

### Configuración para desarrollador solo

Si trabajás solo en el repo, la protección se configura así:

- **Requerir Pull Request antes de mergear**, con **0 aprobaciones requeridas.**
  No podés aprobar tu propio PR, así que exigir aprobaciones te trabaría a vos
  mismo. Lo que se exige no es el visto bueno humano, sino el de la máquina.
- **Requerir que el check `test` pase** antes de habilitar el merge. Ese es el
  guardián real: aunque no haya un segundo par de ojos, el código no entra si los
  tests no están en verde.

Así conservás el flujo de PR (historial limpio, checks automáticos, lugar para el
review con IA a futuro) sin bloquearte por una aprobación que nadie puede dar.

---

## 6. Security Review y Code Review automáticos con IA (paso futuro — NO activado)

Existe la GitHub Action oficial de Anthropic
[`claude-code-security-review`](https://github.com/anthropics/claude-code-security-review):
analiza cada PR con Claude y **comenta las vulnerabilidades que encuentra** —
inyecciones, autenticación débil, exposición de datos sensibles, lógica insegura—
directamente en el diff. Es la versión automática del par de ojos de seguridad
que un proyecto chico raramente tiene.

**Hoy NO está activada, y es una decisión consciente:** correrla en cada PR
consume créditos de la API. Se prende cuando el proyecto justifique ese gasto.

### Cómo activarla cuando se quiera

1. En GitHub, ir a **Settings > Secrets and variables > Actions** del repo y
   agregar el secreto **`ANTHROPIC_API_KEY`** (nunca hardcodeada en el código ni
   en el workflow — ver la prohibición en `AGENTS.md`).
2. Agregar el workflow de la action al directorio `.github/workflows/`, siguiendo
   el README del repo oficial.

### Alternativas de code review con IA

Para revisión de código (calidad, no solo seguridad) hay opciones que se integran
al PR: **CodeRabbit** y **GitHub Copilot** (code review) comentan sugerencias
sobre el diff. Sirven como capa extra, pero **no reemplazan** que el humano
entienda el cambio: la IA comenta patrones, el humano decide qué aplica al
negocio.

---

## 7. Release Please: versionado y releases automáticos

[Release Please](https://github.com/googleapis/release-please) (de Google)
automatiza el versionado a partir de los conventional commits:

1. Tras cada merge a `main`, crea (o actualiza) un **Release PR** que sube la
   versión y acumula el changelog.
2. Cuando mergeás ese Release PR, crea el **tag `vX.Y.Z`**, el **GitHub Release**
   y las **release notes**, todo derivado de los mensajes de commit.

Por eso los **conventional commits son obligatorios** (sección 3): release-please
lee los prefijos para decidir si el cambio es un `fix:` (sube el patch), un
`feat:` (sube el minor) o un breaking change (sube el major). Sin prefijos
consistentes, el versionado automático no puede funcionar y hay que hacerlo a
mano —justo lo que este flujo elimina—.

---

## Checklist antes de abrir un PR

Antes de abrir el Pull Request, verificá:

- [ ] **Trabajás en una rama, no en `main`.** Nada de push directo a `main`.
- [ ] **Los tests offline pasan localmente:** corriste los `parser/test_*.py`
      afectados con `python3 parser/test_X.py` y están en verde.
- [ ] **El cambio de comportamiento tiene test.** Si cambiaste lógica de negocio
      o un edge case, hay un test que lo cubre — y entendés por qué pasa.
- [ ] **No introdujiste pytest** ni ninguna dependencia que rompa la convención
      standalone.
- [ ] **Ningún secreto en el diff.** `ANTHROPIC_API_KEY` y cualquier credencial
      van por `.env`/entorno, nunca hardcodeados ni en logs.
- [ ] **No commiteaste `parser/datos_clinica_real/`** ni datos reales de clínica.
- [ ] **Los mensajes de commit son conventional commits** (`feat:`, `fix:`,
      `chore:`…) para que release-please los procese.
- [ ] **Revisaste el diff completo vos mismo.** Si la IA lo escribió, lo leíste
      entero y entendés cada línea. Sos el responsable, no el modelo.

Con esto, cuando abras el PR el CI corre lint + validaciones + tests, y si todo
queda en verde, el cambio está listo para entrar a una `main` siempre desplegable.
