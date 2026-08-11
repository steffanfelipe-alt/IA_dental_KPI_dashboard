"use client";

import { MetricCard } from "@/components/veredicto/MetricCard";
import type { MetricaCalculada } from "@/lib/types/metricas";

/**
 * components/veredicto/MetricasGrid.tsx
 *
 * Spec "veredicto-metrics-layout": one rectangle per metric in a 4-column
 * CSS grid that wraps into additional rows instead of scrolling
 * horizontally — the previous `overflow-x-auto` flex row hid metrics
 * past the first screenful behind an undiscoverable horizontal scroll.
 * Any overflow now scrolls vertically with the rest of the page (the
 * parent `Veredicto` `<main>` has no fixed height/overflow clip already).
 * Responsive down to 1 column on mobile, 2 on `sm`, 4 from `lg` up.
 */
export function MetricasGrid({
  metricas,
  onSelect,
}: {
  metricas: MetricaCalculada[];
  onSelect: (kpiId: number) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {metricas.map((metrica) => (
        <MetricCard key={metrica.kpi_id} metrica={metrica} onClick={() => onSelect(metrica.kpi_id)} />
      ))}
    </div>
  );
}
