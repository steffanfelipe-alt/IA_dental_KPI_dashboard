"use client";

import { Line, LabelList, LineChart, ResponsiveContainer, XAxis } from "recharts";

/**
 * components/veredicto/PeriodChart.tsx
 *
 * Large line chart for the metric fullscreen detail (spec "Metric detail
 * shows chart, per-period numbers, importance, and devolución": "gráfico
 * grande con números de cada período"). Unlike `Sparkline`, this renders
 * an `XAxis` with period labels and a `LabelList` printing each point's
 * value directly on the line.
 */
export function PeriodChart({ serie }: { serie: Record<string, number> }) {
  const data = Object.entries(serie).map(([periodo, valor]) => ({ periodo, valor }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 24, right: 24, left: 8, bottom: 8 }}>
          <XAxis
            dataKey="periodo"
            tickLine={false}
            axisLine={{ stroke: "#e5e7eb" }}
            tick={{ fontSize: 12, fill: "#6b7280" }}
          />
          <Line
            type="monotone"
            dataKey="valor"
            stroke="#2563eb"
            strokeWidth={2}
            dot={{ r: 4, fill: "#2563eb" }}
            isAnimationActive={false}
          >
            <LabelList dataKey="valor" position="top" fill="#111827" fontSize={12} />
          </Line>
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
