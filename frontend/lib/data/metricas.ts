/**
 * lib/data/metricas.ts
 *
 * SPEC §10 endpoint: `GET /api/v1/clinicas/{clinicaId}/metricas/{slug} →
 * { metrica, acciones }`. Pantalla D (`/metricas/[slug]`, PR3) is the
 * only planned caller; `acciones: AccionSobreMetrica[]` is derived here
 * from `lib/mock/sistemas.ts` (which system, still to apply, would move
 * this metric and by how much) rather than hand-duplicated as separate
 * fixtures — same underlying facts, one source.
 *
 * Same seam and `clinicaId`-from-session invariant as `lib/data/panel.ts`
 * — see that file's header, it applies here unchanged.
 */
import type { AccionSobreMetrica, Metrica, MetricaConObjetivoSistema } from "@/lib/types";
import { MOCK_METRICAS } from "@/lib/mock/panel";
import { MOCK_SISTEMAS } from "@/lib/mock/sistemas";

export interface MetricaConAcciones {
  metrica: Metrica;
  acciones: AccionSobreMetrica[];
}

function calcularImpactoEstimadoPct(metrica: MetricaConObjetivoSistema): number {
  if (metrica.objetivoPostSistema === null) {
    return 0;
  }
  const base = Math.max(Math.abs(metrica.valorActual), 1);
  return Math.round(((metrica.objetivoPostSistema - metrica.valorActual) / base) * 1000) / 10;
}

function accionesParaMetrica(slug: string): AccionSobreMetrica[] {
  return MOCK_SISTEMAS.filter((sistema) => sistema.estado !== "implementado").flatMap((sistema) => {
    const metricaEnSistema = sistema.metricas.find((m) => m.slug === slug);
    if (!metricaEnSistema || metricaEnSistema.objetivoPostSistema === null) {
      return [];
    }
    return [
      {
        sistema: { slug: sistema.slug, nombre: sistema.nombre, estado: sistema.estado },
        impactoEstimadoPct: calcularImpactoEstimadoPct(metricaEnSistema),
        valorProyectado: metricaEnSistema.objetivoPostSistema,
        porQueServiria: sistema.motivoSugerencia ?? sistema.descripcionCorta,
      } satisfies AccionSobreMetrica,
    ];
  });
}

export async function getMetrica(clinicaId: string, slug: string): Promise<MetricaConAcciones | null> {
  void clinicaId;
  const metrica = MOCK_METRICAS.find((m) => m.slug === slug);
  if (!metrica) {
    return null;
  }
  return { metrica, acciones: accionesParaMetrica(slug) };
}
