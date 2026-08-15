/**
 * lib/data/ventana.ts
 *
 * Shared "period window" helper, extracted verbatim out of
 * `lib/data/panel.ts` (Slice 2 Front B, WU-B1) so `lib/data/sistemas.ts`
 * can apply the exact same `?periodo=` windowing semantics instead of
 * re-implementing them. Behavior is unchanged from the original
 * `panel.ts` implementation — see `getPanel`'s doc comment there for the
 * caller-facing contract, this file only moved the implementation.
 */
import type { Metrica } from "@/lib/types";
import { PERIODOS_24M } from "@/lib/mock/panel";

/**
 * `?periodo=` (`PeriodPicker`, `panel/page.tsx`) → number of most-recent
 * REAL months to window `valorActual`/`valorAnterior` by. An
 * unrecognized/absent `periodo` intentionally has no entry here — callers
 * keep today's full-serie behavior untouched in that case, see the guard
 * in each loader.
 */
export const VENTANA_POR_PERIODO: Record<string, number> = {
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
export function aplicarVentanaPeriodo(metrica: Metrica, n: number): Metrica {
  const puntosReales = metrica.serie.filter((punto) => !punto.proyectado);
  const ventanaValida = n >= 2 && n <= PERIODOS_24M.length && puntosReales.length >= n;
  const ventana = ventanaValida ? puntosReales.slice(-n) : puntosReales;
  return {
    ...metrica,
    valorActual: ventana[ventana.length - 1].valor,
    valorAnterior: ventana[0].valor,
  };
}
