import { NextResponse } from "next/server";
import { callApi } from "@/lib/bff/callApi";
import { errorResponse } from "@/lib/bff/errorResponse";
import { setSessionCookies } from "@/lib/bff/sessionCookies";
import type { SessionResponse, SignupRequest } from "@/lib/types/api";

/**
 * POST /api/auth/signup — proxies `POST /auth/signup` (D2). Sets the
 * httpOnly session cookies when Supabase returns an immediate session;
 * when the project requires email confirmation, `access_token` comes
 * back `null` and no cookies are set (spec: "Signup pending email
 * confirmation" — the client routes to /check-email instead).
 *
 * The response body never contains a token either way — only
 * `pending_confirmation` tells the client which screen to show next.
 */
export async function POST(request: Request) {
  try {
    const body = (await request.json()) as SignupRequest;
    const session = await callApi<SessionResponse>("/auth/signup", {
      method: "POST",
      body,
      auth: false,
    });

    if (session.access_token && session.refresh_token) {
      await setSessionCookies(session.access_token, session.refresh_token);
    }

    return NextResponse.json(
      {
        user_id: session.user_id,
        email: session.email,
        pending_confirmation: session.access_token === null,
      },
      { status: 201 },
    );
  } catch (error) {
    return errorResponse(error);
  }
}
