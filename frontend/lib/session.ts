import { hasAccessCookie } from "@/lib/bff/sessionCookies";

/**
 * lib/session.ts
 *
 * Resolves the current clinic id for the logged-in session — the
 * `clinicaId`-from-session invariant `lib/data/{panel,sistemas,metricas}.ts`
 * document but that PR1 deliberately deferred ("no page calls the
 * loaders yet, so there is no real caller to resolve it for"). This PR's
 * `panel/page.tsx` is that first real caller.
 *
 * There is genuinely no backend piece to call yet: the Supabase JWT
 * carries no `clinica_id` claim, and `api/routers/clinicas.py` only has
 * `POST /clinicas` (create) today — no "get the current session's
 * clinica" endpoint. Inventing one here would be backend work smuggled
 * into a frontend-only slice, so this returns a fixed mock id instead,
 * still gated behind the same cookie-presence check `(app)/layout.tsx`
 * already enforces (defense in depth if this is ever called from
 * somewhere outside that gate). Real resolution is Slice 2 work, once
 * that backend endpoint exists.
 */
const CLINICA_ID_MOCK = "clinic-mock-slice-1";

export async function resolverClinicaIdActual(): Promise<string> {
  const autenticado = await hasAccessCookie();
  if (!autenticado) {
    throw new Error("resolverClinicaIdActual: no hay sesión activa.");
  }
  return CLINICA_ID_MOCK;
}
