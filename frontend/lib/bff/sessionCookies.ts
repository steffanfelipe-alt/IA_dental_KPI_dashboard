/**
 * lib/bff/sessionCookies.ts
 *
 * D1 cookie-mutation boundary: this is the ONLY module that writes the
 * session cookies. Everything else (callApi's D1b refresh-retry, the
 * four auth Route Handlers) calls into these functions instead of
 * touching `cookies()` directly, so there is exactly one place that
 * knows the cookie names and options.
 *
 * `cookies()` from `next/headers` is async in this Next.js version and
 * is documented as writable from Route Handlers (not just Server
 * Functions) — see node_modules/next/dist/docs/.../functions/cookies.md
 * "Setting a cookie ... in a Server Function or Route Handler". That is
 * exactly the context every caller of this module runs in.
 */

import { cookies } from "next/headers";

export const ACCESS_TOKEN_COOKIE = "access_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

// Supabase's default access-token TTL is 3600s; refresh tokens are
// rotation-based server-side (no fixed backend expiry), so this maxAge
// is a BFF-side "stay logged in" window, not a security boundary. Both
// are env-tunable — see design's open question ("align access-cookie
// max-age with actual Supabase session config"), which is deferred here
// to the real Supabase project's dashboard settings at deploy time.
const ACCESS_TOKEN_MAX_AGE_SECONDS = Number(process.env.AUTH_ACCESS_COOKIE_MAX_AGE_SECONDS ?? 60 * 60);
const REFRESH_TOKEN_MAX_AGE_SECONDS = Number(
  process.env.AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS ?? 60 * 60 * 24 * 30,
);

// Spec: "httpOnly Secure SameSite=Lax cookie". `secure: true` unconditionally
// (not gated on NODE_ENV) — modern browsers treat http://localhost as a
// secure context, so this also works in local dev without weakening the
// production requirement.
const BASE_COOKIE_OPTIONS = {
  httpOnly: true,
  secure: true,
  sameSite: "lax" as const,
  path: "/",
};

export function accessCookieOptions() {
  return { ...BASE_COOKIE_OPTIONS, maxAge: ACCESS_TOKEN_MAX_AGE_SECONDS };
}

export function refreshCookieOptions() {
  return { ...BASE_COOKIE_OPTIONS, maxAge: REFRESH_TOKEN_MAX_AGE_SECONDS };
}

export async function setSessionCookies(accessToken: string, refreshToken: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(ACCESS_TOKEN_COOKIE, accessToken, accessCookieOptions());
  cookieStore.set(REFRESH_TOKEN_COOKIE, refreshToken, refreshCookieOptions());
}

export async function clearSessionCookies(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(ACCESS_TOKEN_COOKIE, "", { ...BASE_COOKIE_OPTIONS, maxAge: 0 });
  cookieStore.set(REFRESH_TOKEN_COOKIE, "", { ...BASE_COOKIE_OPTIONS, maxAge: 0 });
}

export async function readAccessToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;
}

export async function readRefreshToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
}

export async function hasAccessCookie(): Promise<boolean> {
  const cookieStore = await cookies();
  return cookieStore.has(ACCESS_TOKEN_COOKIE);
}
