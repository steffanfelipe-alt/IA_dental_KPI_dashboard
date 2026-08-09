import { NextResponse } from "next/server";
import { refreshAccessToken } from "@/lib/bff/callApi";

/**
 * POST /api/auth/refresh — explicit BFF refresh proxy (D1b/D2) for a
 * client-initiated "renew my session" call. Reuses the exact same
 * `refreshAccessToken` that `callApi` calls internally on a 401 (D1b),
 * so there is exactly one implementation of the rotate-cookies-or-clear
 * decision in the whole BFF.
 *
 * Takes no request body: the refresh token lives in an httpOnly cookie
 * the browser can't read anyway, so `refreshAccessToken` reads it
 * server-side instead of expecting the client to resend it.
 *
 * On failure this clears both cookies (inside `refreshAccessToken`) and
 * returns 401 — it does NOT issue an HTTP redirect. This endpoint is
 * called via `fetch`, not full-page navigation, so a redirect response
 * would hand the caller an HTML login page instead of JSON. Routing to
 * /login is the client's job on seeing this 401; on the next
 * server-rendered navigation the D1d layout gate redirects automatically
 * anyway, because the access cookie is now gone.
 */
export async function POST() {
  const newAccessToken = await refreshAccessToken();
  if (!newAccessToken) {
    return NextResponse.json(
      { error: { codigo: 401, mensaje: "La sesión expiró o el refresh token es inválido." } },
      { status: 401 },
    );
  }
  return NextResponse.json({ refreshed: true });
}
