"use client";

import { Line, LineChart, ResponsiveContainer } from "recharts";

/**
 * components/veredicto/Sparkline.tsx
 *
 * Small, axis-less line chart used inside a `MetricCard` (spec "Metric
 * rectangle shows chart, value, and period labels": "gráfico chico de
 * períodos a la derecha"). Fixed small footprint, no axes/grid/tooltip —
 * just the trend line for the metric's period series.
 */
export function Sparkline({ serie }: { serie: Record<string, number> }) {
  const data = Object.entries(serie).map(([periodo, valor]) => ({ periodo, valor }));

  return (
    <div className="h-12 w-20 shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="valor"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
