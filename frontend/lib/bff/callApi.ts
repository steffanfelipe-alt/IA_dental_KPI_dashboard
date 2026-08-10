/**
 * lib/bff/callApi.ts
 *
 * Shared fetch wrapper for every BFF Route Handler (design D2). A single
 * Route Handler still exists per backend endpoint (explicit, typed,
 * per-route runtime/validation), but they all funnel their actual
 * FastAPI call through this function, which centralizes three concerns
 * so no individual route re-implements them:
 *
 *   - D1b: Bearer-token injection from the `access_token` cookie, plus a
 *     silent refresh-and-retry-once on a 401.
 *   - D6: normalizing `{error:{codigo,mensaje,detalle}}` (or any other
 *     non-2xx response) into a typed `ApiError`.
 *   - D7: per-route fetch cache mode (`no-store` vs `revalidate`).
 */

import { readAccessToken, readRefreshToken, setSessionCookies, clearSessionCookies } from "@/lib/bff/sessionCookies";
import { ApiError, isApiErrorEnvelope } from "@/lib/types/errors";
import type { SessionResponse } from "@/lib/types/api";

const BACKEND_API_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

export type CacheMode = { mode: "no-store" } | { mode: "revalidate"; seconds: number };

export interface CallApiOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  /** Pass a `FormData` body as-is (no JSON.stringify, no manual Content-Type — see PR2's `migrar` route). */
  isMultipart?: boolean;
  /** D7 — defaults to `{ mode: "no-store" }` when omitted. */
  cache?: CacheMode;
  /**
   * Whether to inject `Authorization: Bearer <access_token>` from the
   * session cookie and attempt the D1b refresh-retry-once flow on a 401.
   * MUST be `false` for the unauthenticated auth proxies
   * (signup/login) — there is no access token to send yet, and a 401
   * from those endpoints means "bad credentials", not "expired token",
   * so retrying via refresh would be both wrong and misleading.
   * Defaults to `true`.
   */
  auth?: boolean;
}

function buildFetchCacheInit(cache?: CacheMode): { cache?: RequestCache; next?: { revalidate: number } } {
  if (!cache || cache.mode === "no-store") {
    return { cache: "no-store" };
  }
  return { next: { revalidate: cache.seconds } };
}

function buildRequestInit(options: CallApiOptions, bearerToken?: string): RequestInit {
  const headers = new Headers(options.headers);
  if (bearerToken) {
    headers.set("Authorization", `Bearer ${bearerToken}`);
  }

  if (options.isMultipart) {
    // Never set Content-Type manually for multipart bodies — fetch
    // derives the boundary from the FormData instance itself; setting it
    // by hand strips the boundary and the backend can't parse the parts.
    return { method: options.method ?? "POST", headers, body: options.body as FormData };
  }

  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    return { method: options.method ?? "POST", headers, body: JSON.stringify(options.body) };
  }

  return { method: options.method ?? "GET", headers };
}

async function doFetch(path: string, init: RequestInit, cache?: CacheMode): Promise<Response> {
  return fetch(`${BACKEND_API_URL}${path}`, { ...init, ...buildFetchCacheInit(cache) });
}

/** D6: turn any non-2xx response into a typed `ApiError`, envelope or not. */
async function parseErrorEnvelope(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON error body (network/proxy failure, empty body, etc.) —
    // fall back to a synthetic envelope below so every failure surfaces
    // the same ApiError shape regardless of what the backend actually sent.
  }
  if (isApiErrorEnvelope(body)) {
    return new ApiError(body.error);
  }
  return new ApiError({
    codigo: response.status,
    mensaje: response.statusText || "Error de red inesperado.",
  });
}

/**
 * D1b: attempt exactly one silent refresh using the refresh_token
 * cookie, rotate both cookies on success, and return the new access
 * token. Returns `null` (and clears both cookies) on any failure —
 * missing refresh cookie, backend rejecting it, or a malformed session
 * response — so callers never have to distinguish "no refresh token"
 * from "refresh token rejected".
 *
 * Exported so the explicit `POST /api/auth/refresh` Route Handler (D2)
 * reuses this exact logic instead of re-implementing it — there is only
 * one rotate-or-clear decision in the whole BFF.
 */
export async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = await readRefreshToken();
  if (!refreshToken) {
    await clearSessionCookies();
    return null;
  }

  const response = await fetch(`${BACKEND_API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });

  if (!response.ok) {
    await clearSessionCookies();
    return null;
  }

  const session = (await response.json()) as SessionResponse;
  if (!session.access_token || !session.refresh_token) {
    await clearSessionCookies();
    return null;
  }

  await setSessionCookies(session.access_token, session.refresh_token);
  return session.access_token;
}

export async function callApi<T>(path: string, options: CallApiOptions = {}): Promise<T> {
  const useAuth = options.auth ?? true;
  const bearerToken = useAuth ? await readAccessToken() : undefined;

  const response = await doFetch(path, buildRequestInit(options, bearerToken), options.cache);

  if (response.ok) {
    // 204 No Content (e.g. `PUT /onboarding/{id}/respuestas`) has no body
    // to parse — calling response.json() on it throws a SyntaxError.
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  if (useAuth && response.status === 401) {
    const newAccessToken = await refreshAccessToken();
    if (!newAccessToken) {
      // refreshAccessToken already cleared the cookies on this path.
      throw await parseErrorEnvelope(response);
    }

    const retryResponse = await doFetch(path, buildRequestInit(options, newAccessToken), options.cache);
    if (retryResponse.ok) {
      if (retryResponse.status === 204) {
        return undefined as T;
      }
      return (await retryResponse.json()) as T;
    }
    if (retryResponse.status === 401) {
      // The refreshed token still isn't accepted — the session is
      // genuinely invalid. Clear cookies and surface 401 to the client;
      // no second refresh attempt (that would risk an infinite loop).
      await clearSessionCookies();
    }
    throw await parseErrorEnvelope(retryResponse);
  }

  throw await parseErrorEnvelope(response);
}
