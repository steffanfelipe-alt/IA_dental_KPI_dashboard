/**
 * lib/data/panel.ts
 *
 * SPEC §10 endpoint: `GET /api/v1/clinicas/{clinicaId}/panel?periodo= →
 * { metricas, sistemasEnCurso }`. This loader is the frontend's "port"
 * for Pantalla A (hexagonal seam, see design + this PR's description):
 * `panel/page.tsx` (a later PR) calls `getPanel(clinicaId, periodo)` and
 * never touches `lib/mock/*` or a `fetch` call directly. Today the body
 * returns the mocks; Slice 2 swaps the body for a `callApi` BFF fetch —
 * this exact signature does not change, so no caller is touched.
 *
 * SECURITY INVARIANT (SPEC §10): `clinicaId` MUST come from the caller
 * resolving it from the session server-side — NEVER from an editable
 * `searchParams` value. This function trusts its caller on that; it does
 * not (and Slice 2's real implementation must not) accept `clinicaId`
 * from anywhere else.
 */
import type { Metrica, Sistema } from "@/lib/types";
import { MOCK_METRICAS } from "@/lib/mock/panel";
import { MOCK_SISTEMAS } from "@/lib/mock/sistemas";

export interface PanelData {
  metricas: Metrica[];
  /**
   * Endpoint doc names this `sistemasEnCurso`, but Pantalla A's A3 block
   * (SPEC) shows `en_proceso`/`sugerido`/`implementado` PLUS the manually
   * anchored `disponible` systems (A3-bis) — so this is the full
   * panel-relevant set, not literally only "in progress" ones. The
   * display-only ordering/exclusion rules (never show a non-anchored
   * `disponible` system) belong to the Pantalla A component, not here.
   */
  sistemasEnCurso: Sistema[];
}

function esRelevantePanel(sistema: Sistema): boolean {
  return sistema.estado !== "disponible" || sistema.anclado;
}

const MOCK_PANEL: PanelData = {
  metricas: MOCK_METRICAS,
  sistemasEnCurso: MOCK_SISTEMAS.filter(esRelevantePanel),
};

export async function getPanel(clinicaId: string, periodo?: string): Promise<PanelData> {
  // Slice 1: mocks are static, so `clinicaId`/`periodo` are unused here —
  // both are still required params so the signature already matches what
  // the Slice 2 BFF call needs (`?periodo=` query, `clinicaId`-scoped
  // path), and callers don't change when the body does.
  void clinicaId;
  void periodo;
  return MOCK_PANEL;
}
