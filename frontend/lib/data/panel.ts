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
import { MOCK_METRICAS, PERIODOS_24M } from "@/lib/mock/panel";
import { MOCK_SISTEMAS } from "@/lib/mock/sistemas";

export interface PanelData {
  metricas: Metrica[];
  /**
   * Endpoint doc names this `sistemasEnCurso`, but Pantalla A's A3 block
   * (SPEC) shows `en_proceso`/`sugerido`/`implementado` PLUS the manually
   * anchored `disponible` systems (A3-bis) — so this is the FULL system
   * list, unfiltered. The display-only ordering/exclusion rules (never
   * show a non-anchored `disponible` system in A3, anchor/unanchor
   * interaction, max-4 gate) belong to `components/systems/SystemsBlock`
   * (Phase 4/PR2), not this loader — see that component's header.
   */
  sistemasEnCurso: Sistema[];
}

const MOCK_PANEL: PanelData = {
  metricas: MOCK_METRICAS,
  sistemasEnCurso: MOCK_SISTEMAS,
};

/**
 * `?periodo=` (`PeriodPicker`, `panel/page.tsx`) → number of most-recent
 * REAL months to window `valorActual`/`valorAnterior` by. An
 * unrecognized/absent `periodo` (e.g. the loader called without one, as
 * every caller before this change did) intentionally has no entry here —
 * `getPanel` keeps today's full-serie behavior untouched in that case,
 * see the guard below.
 */
const VENTANA_POR_PERIODO: Record<string, number> = {
  "3m": 3,
  "6m": 6,
  "12m": 12,
};

/**
 * `valorAnterior` = the FIRST point of the selected window (not the
 * point right before `valorActual`), so the delta reflects the FULL
 * chosen horizon and actually changes across 3m/6m/12m — confirmed
 * design decision (SPEC "Functional Period Window"). The chart itself
 * keeps rendering `metrica.serie` in full; only these two scalars are
 * windowed.
 *
 * Guard: `PERIODOS_24M` (`lib/mock/panel.ts`) is the reference for how
 * many real periods actually exist. If the requested window doesn't fit
 * the real (non-projected) points available for this metric — or
 * doesn't fit within `PERIODOS_24M` itself — fall back to the full real
 * serie as the window (oldest real point becomes `valorAnterior`)
 * instead of slicing something shorter than intended.
 */
function aplicarVentanaPeriodo(metrica: Metrica, n: number): Metrica {
  const puntosReales = metrica.serie.filter((punto) => !punto.proyectado);
  const ventanaValida = n >= 2 && n <= PERIODOS_24M.length && puntosReales.length >= n;
  const ventana = ventanaValida ? puntosReales.slice(-n) : puntosReales;
  return {
    ...metrica,
    valorActual: ventana[ventana.length - 1].valor,
    valorAnterior: ventana[0].valor,
  };
}

export async function getPanel(clinicaId: string, periodo?: string): Promise<PanelData> {
  // Slice 1: mocks are static, so `clinicaId` is unused here — still a
  // required param so the signature already matches what the Slice 2 BFF
  // call needs (`clinicaId`-scoped path), and callers don't change when
  // the body does.
  void clinicaId;

  const n = periodo ? VENTANA_POR_PERIODO[periodo] : undefined;
  if (n === undefined) {
    // No `periodo`, or a value outside `3m`/`6m`/`12m`: today's full-serie
    // behavior, unchanged — the mock's own `valorActual`/`valorAnterior`.
    return MOCK_PANEL;
  }

  return {
    ...MOCK_PANEL,
    metricas: MOCK_PANEL.metricas.map((metrica) => aplicarVentanaPeriodo(metrica, n)),
  };
}
