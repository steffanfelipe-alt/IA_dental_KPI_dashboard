/**
 * lib/types/errors.ts
 *
 * Typed contract for the uniform error envelope every FastAPI response
 * uses (see `api/errores.py`): `{"error":{"codigo","mensaje","detalle"}}`
 * for both `HTTPException` (401/403/404/409/…) and Pydantic validation
 * failures (422, where `detalle` is the `RequestValidationError.errors()`
 * list — design D6: "map detalle[] to per-field errors").
 */

export interface ApiErrorBody {
  codigo: number;
  mensaje: string;
  detalle?: unknown;
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody;
}

/**
 * Thrown by `callApi` (D6) for every non-2xx response, whether the
 * backend sent a proper envelope or not (see `isApiErrorEnvelope` — a
 * malformed/non-JSON error body still becomes an `ApiError`, built from
 * the raw HTTP status, so callers never have to branch on "did the
 * backend actually send our envelope shape".
 */
export class ApiError extends Error {
  readonly codigo: number;
  readonly detalle?: unknown;

  constructor(body: ApiErrorBody) {
    super(body.mensaje);
    this.name = "ApiError";
    this.codigo = body.codigo;
    this.detalle = body.detalle;
  }
}

export function isApiErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const candidate = (value as { error?: unknown }).error;
  return (
    typeof candidate === "object" &&
    candidate !== null &&
    "codigo" in candidate &&
    "mensaje" in candidate
  );
}
