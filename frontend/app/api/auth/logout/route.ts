import { NextResponse } from "next/server";
import { clearSessionCookies } from "@/lib/bff/sessionCookies";

/**
 * POST /api/auth/logout — D1c. There is no backend `/auth/logout`
 * endpoint (see api/routers/auth.py): Supabase JWT invalidation is a
 * client-side concern, and the anon-key client this API uses has
 * nothing server-side to revoke. Logout is therefore purely a BFF-side
 * cookie clear.
 */
export async function POST() {
  await clearSessionCookies();
  return NextResponse.json({ ok: true });
}
