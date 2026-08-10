import { redirect } from "next/navigation";
import { readAccessToken } from "@/lib/bff/sessionCookies";
import type { EstadoResponse } from "@/lib/types/api";

const BACKEND_API_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

export type EstadoFetchResult = { ok: true; estado: EstadoResponse } | { ok: false; status: number };

/**
 * Read-only, single-shot `estado` fetch for Server Components. Deliberately
 * does NOT go through `lib/bff/callApi.ts`: on a 401, `callApi`'s D1b
 * refresh-retry calls `setSessionCookies`/`clearSessionCookies`, and
 * Next.js does not support writing cookies during Server Component
 * rendering — see `node_modules/next/dist/docs/01-app/03-api-reference/
 * 04-functions/cookies.md`: "Setting cookies is not supported during
 * Server Component rendering. To modify cookies, invoke a Server Function
 * from the client or use a Route Handler." That write-capable
 * refresh-retry stays exclusively inside Route Handlers (design D1's
 * cookie-mutation boundary) — a 401 here just redirects to `/login` with
 * no refresh attempt, same spirit as D6's "401 (after refresh fail) ->
 * redirect /login".
 *
 * Exported (not just used locally) so `estado/page.tsx` — a Server
 * Component too — reuses this exact function instead of re-implementing
 * it; that page needs its own fresh read anyway for its own
 * `completo`/`migracion_completada` checks (see that file).
 */
export async function fetchEstadoReadOnly(clinicaId: string): Promise<EstadoFetchResult> {
  const accessToken = await readAccessToken();
  if (!accessToken) {
    return { ok: false, status: 401 };
  }

  const response = await fetch(`${BACKEND_API_URL}/onboarding/${clinicaId}/estado`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });

  if (!response.ok) {
    return { ok: false, status: response.status };
  }

  return { ok: true, estado: (await response.json()) as EstadoResponse };
}

/**
 * Design D4: every wizard step scoped to a clinic (`upload`, `conflictos`,
 * `guia`, `estado`) fetches `estado` server-side and redirects backward
 * when a prerequisite isn't met.
 *
 * A layout has no documented way to read the current sub-route's
 * pathname in the App Router — Server Components, unlike Client
 * Components via `usePathname`, do not receive it; see
 * `node_modules/next/dist/docs/01-app/03-api-reference/03-file-
 * conventions/layout.md`: "Layouts do not re-render on navigation, so
 * they do not access pathname... use usePathname in a Client Component
 * instead." Verified against that doc rather than assumed — this is a
 * real Next.js 16 constraint, not a design shortcut. Consequently this
 * layout enforces only the ONE guard that's uniform across every child
 * route regardless of which one it is: the clinic must exist, belong to
 * this user, and the session must still be valid — the same shape as
 * `(app)/layout.tsx`'s D1d gate (a single uniform check, not a per-route
 * one). The route-SPECIFIC backward redirects (e.g. "no /conflictos or
 * /guia before migracion_completada") live in each leaf page instead
 * (`conflictos/page.tsx`, `estado/page.tsx` in this batch — each
 * inherently knows its own identity just by being that file, no pathname
 * needed; `guia/page.tsx`, built in parallel outside this batch, should
 * add the equivalent `migracion_completada` check for the same reason).
 */
export default async function OnboardingClinicaLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await fetchEstadoReadOnly(id);

  if (!result.ok) {
    // 401: no/invalid session — bounce to login, no refresh attempted
    // (see fetchEstadoReadOnly's comment). Anything else (403 not owner,
    // 404 clinic doesn't exist, 5xx): no dedicated "no access" page
    // exists yet in this batch's scope (design D6 defers that), so the
    // authenticated home is the safe fallback.
    redirect(result.status === 401 ? "/login" : "/");
  }

  return <>{children}</>;
}
