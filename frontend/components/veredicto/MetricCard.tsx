"use client";

import { Sparkline } from "@/components/veredicto/Sparkline";
import type { MetricaCalculada } from "@/lib/types/metricas";

/**
 * components/veredicto/MetricCard.tsx
 *
 * One rectangle per metric in the Métricas grid (spec "Metric rectangle
 * shows chart, value, and period labels"): small chart on the right,
 * the metric value in large text, small period labels below the value.
 * Clicking opens the fullscreen drill-down (spec "Clicking a metric
 * opens its fullscreen detail").
 *
 * Metrics without a period series (`serie: null`, kpi_id 17-20 in the
 * mock — see `lib/mock/veredicto.ts`) render without the sparkline/period
 * row; only the value is shown for those.
 */
export function MetricCard({ metrica, onClick }: { metrica: MetricaCalculada; onClick: () => void }) {
  const periodos = metrica.serie ? Object.keys(metrica.serie) : [];

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-64 shrink-0 flex-col justify-between gap-3 rounded-2xl border border-black/5 bg-white p-5 text-left shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-ink-600">{metrica.nombre}</p>
          <p className="mt-1 text-3xl font-semibold text-ink-900">
            <span>{metrica.valor}</span>{" "}
            <span className="text-sm font-normal text-ink-600">{metrica.unidad}</span>
          </p>
        </div>
        {metrica.serie ? <Sparkline serie={metrica.serie} /> : null}
      </div>

      {periodos.length > 0 ? (
        <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-xs text-ink-600">
          {periodos.map((periodo) => (
            <span key={periodo}>{periodo}</span>
          ))}
        </div>
      ) : null}
    </button>
  );
}
