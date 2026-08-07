# `api/`

FastAPI driving adapter for the dental clinic pipeline. Screaming
Architecture: `parser/` stays the pure domain (screams the dental
domain, owns all business logic); `api/` only translates HTTP↔domain
and owns none. Every route that calls into `parser/` is `def` (sync),
run in FastAPI's threadpool — no route is `async def`, because
`supabase-py` and the Vision/LLM pipeline are sync under the hood and
there is nothing real to `await`.

## Testing: `pytest` here, no-pytest in `parser/`

`api/tests/` uses standard `pytest` + FastAPI's `TestClient`/`httpx`.
This is a deliberate choice, not an inconsistency with `parser/`, which
uses its own standalone no-pytest runner convention (each
`parser/**/test_*.py` module is executable directly with
`python -m parser.<path>.test_foo` and prints `OK <test name>` per
test).

`parser/`'s no-pytest convention predates `api/` and was chosen for
`parser/`'s own reasons (documented in
`sdd/ia_dental_kpi_dashboard/testing-capabilities`). `api/` is a new
layer that testing-capabilities explicitly flagged for re-evaluation
rather than automatically inheriting the no-pytest rule — HTTP-layer
testing benefits materially from `pytest` fixtures and FastAPI's
`TestClient`/`app.dependency_overrides` (dependency injection swapping
is what makes router tests possible without a real Supabase/Anthropic
connection), which the no-pytest convention has no equivalent for.
Two layers, two conventions, on purpose:

- `parser/`: `python -m parser.<path>.test_foo` (no pytest, no fixtures, no collection).
- `api/`: `pytest api/tests -q` (fixtures, `TestClient`, `app.dependency_overrides`, `monkeypatch`).

Run both suites before every commit that touches either layer:

```bash
venv/bin/python -m pytest api/tests -q
venv/bin/python -m parser.persistencia.test_adaptador_supabase
```

## Ownership guard is a TEMPORARY app-level trust boundary

`owner_de_clinica` (`api/deps.py`) is the only thing standing between
an authenticated user and any other user's clínica data: it loads
`owner_id` via the repository and 403s on mismatch, 404s if the
clínica doesn't exist. **Row Level Security (RLS) policies on the
Supabase tables are explicitly out of scope for this change** — the
database itself enforces nothing yet. Every read/write in
`AdaptadorSupabase` runs with the `service_role` key, which bypasses
RLS entirely even if policies existed.

This means: if `owner_de_clinica` (or any future route that skips it)
has a bug, or if a new route is added without wiring it through
`OwnerDeClinicaDep`, there is currently **no second line of defense**
at the database layer. Anyone touching auth/ownership code in `api/`
needs to know this. Adding RLS policies (and moving enforcement down
to the database, with `api/`'s guard becoming defense-in-depth rather
than the only gate) is the next planned change, not part of this one.

## Endpoints

| Endpoint | What it does |
|---|---|
| `POST /auth/signup` | Creates a Supabase Auth user, returns session tokens (may be `null` if email confirmation is required). |
| `POST /auth/login` | Authenticates an existing user, returns session tokens. |
| `POST /clinicas` | Creates a clínica; `owner_id` always comes from the authenticated user, never the request body. |
| `POST /onboarding/{clinica_id}/migrar` | Uploads file(s) (413/415 on oversized/unsupported), runs `procesar_migracion`, saves variables, marks migration completed. |
| `POST /onboarding/{clinica_id}/resolver-conflicto` | Applies the owner's choice on a pending variable conflict and re-saves variables. |
| `GET /onboarding/{clinica_id}/guia` | Required onboarding questions merged with already-saved answers. |
| `PUT /onboarding/{clinica_id}/respuestas` | Saves/updates onboarding question answers (204 No Content). |
| `GET /onboarding/{clinica_id}/estado` | Onboarding completeness gate — exposes `migracion_completada` and `preguntas_faltantes` separately, plus the combined `completo`. |
| `GET /clinicas/{clinica_id}/diagnostico` | Deterministic recompute of the structured diagnóstico (no LLM); 409 if onboarding isn't complete. |
| `POST /clinicas/{clinica_id}/informe` | Generate-once narrative report: returns the cached report if one exists, otherwise runs the diagnóstico pipeline plus one Anthropic call and persists the result. |
| `GET /clinicas/{clinica_id}/informe` | Returns the persisted report; 404 if none was ever generated. |
