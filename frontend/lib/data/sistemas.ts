/**
 * lib/data/sistemas.ts
 *
 * SPEC §10 endpoints:
 *   `GET /api/v1/clinicas/{clinicaId}/sistemas        → { panorama, catalogo }`
 *   `GET /api/v1/clinicas/{clinicaId}/sistemas/{slug} → Sistema`
 *
 * `getSistemas` returns the flat catalog today (Slice 1); Pantalla B's
 * `panorama` aggregate (PR5) is a small derived summary of this same
 * list, so it doesn't need its own mock/loader — a later PR computes it
 * from `getSistemas`'s result instead of duplicating fixtures.
 *
 * Same seam and `clinicaId`-from-session invariant as `lib/data/panel.ts`
 * — see that file's header, it applies here unchanged.
 */
import type { Sistema } from "@/lib/types";
import { MOCK_SISTEMAS } from "@/lib/mock/sistemas";

export async function getSistemas(clinicaId: string): Promise<Sistema[]> {
  void clinicaId;
  return MOCK_SISTEMAS;
}

export async function getSistema(clinicaId: string, slug: string): Promise<Sistema | null> {
  void clinicaId;
  return MOCK_SISTEMAS.find((sistema) => sistema.slug === slug) ?? null;
}
