"use client";

import { MetricCard } from "@/components/veredicto/MetricCard";
import type { MetricaCalculada } from "@/lib/types/metricas";

/**
 * components/veredicto/MetricasGrid.tsx
 *
 * Spec "Métricas section renders a scrollable horizontal grid": one
 * rectangle per metric, laid out side by side, scrollable with the
 * mouse when there are more metrics than fit on screen. `overflow-x-auto`
 * on a `flex` row gives native mouse-wheel/trackpad horizontal scroll
 * without extra JS.
 */
export function MetricasGrid({
  metricas,
  onSelect,
}: {
  metricas: MetricaCalculada[];
  onSelect: (kpiId: number) => void;
}) {
  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {metricas.map((metrica) => (
        <MetricCard key={metrica.kpi_id} metrica={metrica} onClick={() => onSelect(metrica.kpi_id)} />
      ))}
    </div>
  );
}
