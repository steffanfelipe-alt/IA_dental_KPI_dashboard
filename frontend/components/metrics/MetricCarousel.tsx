import type { Metrica } from "@/lib/types";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { EmptyState } from "@/components/ui/EmptyState";
import { MetricCard } from "./MetricCard";

/**
 * components/metrics/MetricCarousel.tsx
 *
 * One reusable "titled horizontal row of MetricCards" — `panel/page.tsx`
 * renders it TWICE: once for A1 (Métricas principales, pre-sorted by
 * `impactoScore` desc) and once for A2 (Métricas críticas, pre-sorted by
 * `vulnerabilidadScore` desc). Sorting happens server-side in the page
 * (both blocks read `impactoScore`/`vulnerabilidadScore` — "lo calcula
 * el backend" per the wireframe annotation; Slice 1 stands in for that
 * with a plain `.sort()` over the mock), not here — this component is
 * intentionally dumb: it renders whatever order it's given, unmodified,
 * and never deduplicates (SPEC "a metric can appear in both blocks").
 *
 * Horizontal scroll (wireframe's "row" + "scroll horizontal" pattern),
 * built with plain overflow-x rather than a carousel library — matches
 * this app's existing preference for small, dependency-free primitives.
 */
export function MetricCarousel({ titulo, metricas }: { titulo: string; metricas: Metrica[] }) {
  return (
    <section>
      <SectionHeading title={titulo} />
      {metricas.length === 0 ? (
        <EmptyState title="Todavía no hay métricas para mostrar en este bloque." />
      ) : (
        <div className="flex snap-x gap-4 overflow-x-auto pb-2" role="list" aria-label={titulo}>
          {metricas.map((metrica) => (
            <div key={metrica.slug} role="listitem" className="w-72 shrink-0 snap-start">
              <MetricCard metrica={metrica} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
