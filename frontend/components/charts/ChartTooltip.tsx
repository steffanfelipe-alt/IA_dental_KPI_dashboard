"use client";

import type { TooltipProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

/**
 * components/charts/ChartTooltip.tsx
 *
 * Reusable custom-content recharts `<Tooltip>` for categorical,
 * count-primary distribution charts (spec "Distribution Chart Hover"):
 * shows the absolute count AND its derived percentage share of the
 * chart's own dataset. The share is computed in-component as
 * `cantidad / total` — no `PuntoSerie`/`Metrica` type change, `total`
 * is passed in by the caller (the sum of every row's `cantidad` in that
 * chart's dataset).
 *
 * Deliberately NOT wired into time-series charts (`SparkLine`,
 * `MetricChart`, `veredicto/PeriodChart`) — those plot a single metric's
 * value over time, not a categorical count distribution, so a
 * count+share tooltip doesn't apply there.
 */

interface ChartTooltipRow {
  cantidad: number;
  label?: string;
}

export interface ChartTooltipProps extends TooltipProps<ValueType, NameType> {
  /** Sum of every row's `cantidad` in the chart's dataset (Σcantidad). */
  total: number;
}

export function ChartTooltip({ active, payload, total }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const row = payload[0]?.payload as ChartTooltipRow | undefined;
  if (!row) {
    return null;
  }

  const cantidad = row.cantidad;
  // Safe 0% on a zero-total dataset (empty, or every row's cantidad is 0) —
  // guards against NaN/Infinity from a 0/0 or N/0 division.
  const share = total > 0 ? Math.round((cantidad / total) * 100) : 0;

  return (
    <div className="rounded-xl border border-black/5 bg-white px-3 py-2 text-sm shadow-sm">
      <p className="font-medium text-ink-900">{row.label ?? String(payload[0]?.name ?? "")}</p>
      <p className="text-ink-600">
        {cantidad} ({share}%)
      </p>
    </div>
  );
}
