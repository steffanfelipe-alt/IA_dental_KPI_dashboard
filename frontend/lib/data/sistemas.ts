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
 *
 * Slice 2 (WU-B1, "Métricas y estado"): both loaders now accept an
 * optional `periodo` and window every metric via the SAME
 * `aplicarVentanaPeriodo` helper `getPanel` uses (`lib/data/ventana.ts`,
 * extracted from `panel.ts` so both loaders share one window semantics).
 * They also compute `impactoReal` per metric — the signed delta since
 * `Sistema.fechaImplementacion` — so `MetricasEstado` (WU-B2) never has
 * to.
 */
import type { MetricaConObjetivoSistema, Sistema } from "@/lib/types";
import { MOCK_SISTEMAS } from "@/lib/mock/sistemas";
import { aplicarVentanaPeriodo, VENTANA_POR_PERIODO } from "@/lib/data/ventana";

/**
 * `impactoReal = signo(direccion) · (valorActual − valorAlImplementar)` —
 * design "Front B — additive relacion+impactoReal". `signo` flips the
 * sign for `menor_mejor` metrics so a positive `impactoReal` always means
 * "moved in the direction that's good for the clinic", regardless of the
 * metric's own direction.
 *
 * `null` when the system has no `fechaImplementacion` yet (nothing to
 * measure since a date that doesn't exist) — checked by the caller,
 * see `conImpactoReal` — or when `valorAlImplementar` itself is `null`
 * (no anchor recorded for this metric, e.g. a metric added after launch
 * with no historical baseline).
 */
function calcularImpactoReal(metrica: MetricaConObjetivoSistema): number | null {
  if (metrica.valorAlImplementar === null) {
    return null;
  }
  const signo = metrica.direccion === "menor_mejor" ? -1 : 1;
  return signo * (metrica.valorActual - metrica.valorAlImplementar);
}

function conVentanaEImpacto(sistema: Sistema, n: number | undefined): Sistema {
  return {
    ...sistema,
    metricas: sistema.metricas.map((metrica) => {
      // `aplicarVentanaPeriodo` only ever rewrites `valorActual`/
      // `valorAnterior` (both windows still end on the same last real
      // point), so `impactoReal` reads `valorActual` off the ORIGINAL
      // metric — computing it from the windowed copy would be equivalent
      // but this avoids depending on that implementation detail.
      const impactoReal = sistema.fechaImplementacion ? calcularImpactoReal(metrica) : null;
      const ventaneada = n === undefined ? metrica : aplicarVentanaPeriodo(metrica, n);
      return {
        ...ventaneada,
        objetivoPostSistema: metrica.objetivoPostSistema,
        valorAlImplementar: metrica.valorAlImplementar,
        relacion: metrica.relacion,
        impactoReal,
      } satisfies MetricaConObjetivoSistema;
    }),
  };
}

export async function getSistemas(clinicaId: string, periodo?: string): Promise<Sistema[]> {
  void clinicaId;
  const n = periodo ? VENTANA_POR_PERIODO[periodo] : undefined;
  return MOCK_SISTEMAS.map((sistema) => conVentanaEImpacto(sistema, n));
}

export async function getSistema(clinicaId: string, slug: string, periodo?: string): Promise<Sistema | null> {
  void clinicaId;
  const sistema = MOCK_SISTEMAS.find((s) => s.slug === slug);
  if (!sistema) {
    return null;
  }
  const n = periodo ? VENTANA_POR_PERIODO[periodo] : undefined;
  return conVentanaEImpacto(sistema, n);
}
