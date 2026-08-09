/**
 * lib/types/api.ts
 *
 * Typed mirrors of the FastAPI Pydantic schemas this BFF proxies (design
 * D2/Interfaces). Field names match the backend's snake_case exactly
 * (see `api/schemas/*.py`) — no camelCase translation layer, so a diff
 * against the backend schema is a diff against this file too.
 */

// api/schemas/auth.py
export interface SignupRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

// api/schemas/auth.py: SessionResponse. `access_token`/`refresh_token`
// are nullable because Supabase returns no session on signup when the
// project requires email confirmation — see the BFF Session spec's
// "Signup pending email confirmation" scenario.
export interface SessionResponse {
  user_id: string;
  email: string | null;
  access_token: string | null;
  refresh_token: string | null;
}

// api/schemas/clinicas.py
export interface CrearClinicaRequest {
  nombre: string;
}

export interface ClinicaResponse {
  id: string;
  nombre: string;
  owner_id: string;
}

// api/schemas/onboarding.py
export interface PreguntaGuiaResponse {
  id: string;
  texto: string;
  bloque: number;
  nombre_bloque: string;
  nucleo: boolean;
  respuesta: string | null;
}

export interface GuiaResponse {
  preguntas: PreguntaGuiaResponse[];
}

export interface RespuestasRequest {
  respuestas: Record<string, string>;
}

export interface EstadoResponse {
  completo: boolean;
  migracion_completada: boolean;
  preguntas_faltantes: string[];
}

// api/schemas/onboarding.py: ResolverConflictoRequest. `variables_previas`
// is intentionally absent — the backend loads it from the repository, the
// client only ever sends its choice for one conflict.
export interface ResolverConflictoRequest {
  variable: string;
  valor?: unknown;
  valor_manual?: unknown;
  respuestas_diagnostico?: Record<string, string> | null;
  candidatos?: Record<string, unknown>[] | null;
  periodos_de_escalares?: Record<number, string> | null;
}

/**
 * Hand-written defensive types (design D2/Interfaces). `POST
 * /onboarding/{id}/migrar` and `POST /onboarding/{id}/resolver-conflicto`
 * return `dict[str, Any]` on the backend — `api/schemas/onboarding.py`
 * deliberately has no Pydantic model for either (see that file's
 * docstring: mirroring `procesar_migracion`'s ~15 heterogeneous keys in a
 * BaseModel would just desync from `parser/pipeline.py` without gaining
 * real validation). These shapes cover the keys the wizard actually
 * reads; every other key still round-trips via the index signature.
 */
// `parser/cobertura_calidad/conflictos.py`'s `_candidato()`: always has
// `valor`/`archivo`/`fuente`/`confianza`/`explicacion`; `serie`/
// `periodo_vigente`/`etiquetas_originales` only when the winning
// `VariableValue` carried a series. Optional, hand-verified against that
// function rather than guessed — the index signature still covers
// anything else that round-trips.
export interface CandidatoConflicto {
  valor: unknown;
  archivo?: string | null;
  fuente?: string | null;
  confianza?: number;
  explicacion?: string;
  serie?: Record<string, unknown>;
  periodo_vigente?: string | null;
  etiquetas_originales?: Record<string, unknown>;
  [key: string]: unknown;
}

// `parser/pipeline.py`'s `procesar_migracion` builds `conflictos_pendientes`
// as `{variable, tipo, pregunta, opciones, permite_valor_manual}` (see the
// `resultado` dict literal there) — `opciones` is the candidate list built
// by `CandidatoConflicto` above.
export interface Conflicto {
  variable: string;
  tipo?: string;
  pregunta?: string;
  opciones?: CandidatoConflicto[];
  permite_valor_manual?: boolean;
  [key: string]: unknown;
}

export interface MigrarResponse {
  variables: Record<string, unknown>;
  conflictos_pendientes?: Conflicto[];
  archivos_fallidos?: string[];
  [key: string]: unknown;
}

export interface ResolverConflictoResponse {
  variables: Record<string, unknown>;
  [key: string]: unknown;
}
