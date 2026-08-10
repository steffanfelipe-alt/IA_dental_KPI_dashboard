import { NextResponse } from "next/server";
import { callApi } from "@/lib/bff/callApi";
import { errorResponse } from "@/lib/bff/errorResponse";
import { setSessionCookies } from "@/lib/bff/sessionCookies";
import type { LoginRequest, SessionResponse } from "@/lib/types/api";

/**
 * POST /api/auth/login — proxies `POST /auth/login` (D1a/D2), setting
 * the httpOnly session cookies via a Route Handler (the cookie-mutation
 * boundary — never in a Server Component). FastAPI always returns both
 * tokens on success (401 otherwise), so unlike signup there's no
 * "pending confirmation" branch here.
 */
export async function POST(request: Request) {
  try {
    const body = (await request.json()) as LoginRequest;
    const session = await callApi<SessionResponse>("/auth/login", {
      method: "POST",
      body,
      auth: false,
    });

    // access_token/refresh_token are always present on a 200 from
    // /auth/login (see api/routers/auth.py — null user/session raises
    // 401 before returning), so this cast is safe.
    await setSessionCookies(session.access_token as string, session.refresh_token as string);

    return NextResponse.json({ user_id: session.user_id, email: session.email });
  } catch (error) {
    return errorResponse(error);
  }
}
