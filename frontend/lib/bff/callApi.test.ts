import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// In-memory cookie jar standing in for the real `next/headers` cookie
// store, which only exists inside a Next.js request context. This lets
// these tests exercise callApi's actual refresh-retry/cookie-write logic
// without booting the Next.js runtime. `vi.mock` calls are hoisted above
// these imports by Vitest, so `callApi`/`sessionCookies` transparently
// pick up this fake `next/headers` module.
const cookieJar = new Map<string, string>();

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) => (cookieJar.has(name) ? { name, value: cookieJar.get(name)! } : undefined),
    set: (name: string, value: string) => {
      cookieJar.set(name, value);
    },
    has: (name: string) => cookieJar.has(name),
    delete: (name: string) => {
      cookieJar.delete(name);
    },
  })),
}));

import { callApi, refreshAccessToken } from "./callApi";
import { ApiError } from "@/lib/types/errors";
import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "./sessionCookies";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("callApi", () => {
  beforeEach(() => {
    cookieJar.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed JSON on success and sends the Bearer token from the cookie", async () => {
    cookieJar.set(ACCESS_TOKEN_COOKIE, "valid-token");
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValueOnce(jsonResponse({ ok: true }, 200));

    const result = await callApi<{ ok: boolean }>("/clinicas");

    expect(result).toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/clinicas");
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer valid-token");
    expect(init.cache).toBe("no-store");
  });

  it("retries exactly once after a successful refresh on a 401, and returns the retried result", async () => {
    cookieJar.set(ACCESS_TOKEN_COOKIE, "expired-token");
    cookieJar.set(REFRESH_TOKEN_COOKIE, "valid-refresh");

    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // original call
      .mockResolvedValueOnce(
        jsonResponse({ user_id: "u1", email: "a@b.com", access_token: "new-token", refresh_token: "new-refresh" }, 200),
      ) // refresh call
      .mockResolvedValueOnce(jsonResponse({ ok: true }, 200)); // retried original call

    const result = await callApi<{ ok: boolean }>("/clinicas");

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(cookieJar.get(ACCESS_TOKEN_COOKIE)).toBe("new-token");
    expect(cookieJar.get(REFRESH_TOKEN_COOKIE)).toBe("new-refresh");

    const retryInit = fetchMock.mock.calls[2][1] as RequestInit;
    expect((retryInit.headers as Headers).get("Authorization")).toBe("Bearer new-token");
  });

  it("clears cookies and throws once when the refresh call itself fails (no infinite retry loop)", async () => {
    cookieJar.set(ACCESS_TOKEN_COOKIE, "expired-token");
    cookieJar.set(REFRESH_TOKEN_COOKIE, "invalid-refresh");

    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // original call
      .mockResolvedValueOnce(new Response(null, { status: 401 })); // refresh call fails

    await expect(callApi("/clinicas")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    // clearSessionCookies clears via `.set(name, "", {maxAge:0})` (matching
    // real Next.js cookie semantics), not `.delete()` — assert on the
    // resulting empty value rather than cookie presence.
    expect(cookieJar.get(ACCESS_TOKEN_COOKIE)).toBe("");
    expect(cookieJar.get(REFRESH_TOKEN_COOKIE)).toBe("");
  });

  it("clears cookies and throws once when the retried call still 401s (no second refresh attempt)", async () => {
    cookieJar.set(ACCESS_TOKEN_COOKIE, "expired-token");
    cookieJar.set(REFRESH_TOKEN_COOKIE, "valid-refresh");

    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // original call
      .mockResolvedValueOnce(
        jsonResponse({ user_id: "u1", email: "a@b.com", access_token: "new-token", refresh_token: "new-refresh" }, 200),
      ) // refresh succeeds
      .mockResolvedValueOnce(new Response(null, { status: 401 })); // retry still 401

    await expect(callApi("/clinicas")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(cookieJar.get(ACCESS_TOKEN_COOKIE)).toBe("");
    expect(cookieJar.get(REFRESH_TOKEN_COOKIE)).toBe("");
  });

  it("skips Bearer injection and refresh-retry when auth is false (e.g. bad login credentials)", async () => {
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockResolvedValueOnce(jsonResponse({ error: { codigo: 401, mensaje: "Credenciales inválidas." } }, 401));

    await expect(
      callApi("/auth/login", { method: "POST", body: { email: "a@b.com", password: "x" }, auth: false }),
    ).rejects.toMatchObject({ codigo: 401, message: "Credenciales inválidas." });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Headers).has("Authorization")).toBe(false);
  });

  it("maps a non-envelope error response to a synthetic ApiError built from the HTTP status", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response("Internal Server Error", { status: 500, statusText: "Internal Server Error" }),
    );

    await expect(callApi("/clinicas", { auth: false })).rejects.toMatchObject({ codigo: 500 });
  });

  it("maps the {error:{codigo,mensaje,detalle}} envelope (D6), including 422 field-level detalle", async () => {
    const detalle = [{ loc: ["body", "email"], msg: "field required" }];
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      jsonResponse({ error: { codigo: 422, mensaje: "Error de validación en la petición.", detalle } }, 422),
    );

    try {
      await callApi("/clinicas", { auth: false });
      expect.unreachable("callApi should have thrown");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as InstanceType<typeof ApiError>;
      expect(apiError.codigo).toBe(422);
      expect(apiError.message).toBe("Error de validación en la petición.");
      expect(apiError.detalle).toEqual(detalle);
    }
  });

  it("applies the D7 revalidate cache mode instead of no-store when requested", async () => {
    cookieJar.set(ACCESS_TOKEN_COOKIE, "valid-token");
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValueOnce(jsonResponse({ preguntas: [] }, 200));

    await callApi("/onboarding/clinic-1/guia", { cache: { mode: "revalidate", seconds: 3600 } });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit & { next?: { revalidate: number } }];
    expect(init.next).toEqual({ revalidate: 3600 });
    expect(init.cache).toBeUndefined();
  });
});

describe("refreshAccessToken", () => {
  beforeEach(() => {
    cookieJar.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns null without calling fetch when there is no refresh cookie", async () => {
    const fetchMock = vi.spyOn(global, "fetch");

    const result = await refreshAccessToken();

    expect(result).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rotates both cookies and returns the new access token on success", async () => {
    cookieJar.set(REFRESH_TOKEN_COOKIE, "valid-refresh");
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      jsonResponse({ user_id: "u1", email: "a@b.com", access_token: "new-token", refresh_token: "new-refresh" }, 200),
    );

    const result = await refreshAccessToken();

    expect(result).toBe("new-token");
    expect(cookieJar.get(ACCESS_TOKEN_COOKIE)).toBe("new-token");
    expect(cookieJar.get(REFRESH_TOKEN_COOKIE)).toBe("new-refresh");
  });
});
