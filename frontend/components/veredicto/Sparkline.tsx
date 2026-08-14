"use client";

import { Line, LineChart, ResponsiveContainer } from "recharts";
import type { EstadoMetrica } from "@/lib/semantics";

/**
 * components/veredicto/Sparkline.tsx
 *
 * Small, axis-less line chart used inside a `MetricCard` (spec "Metric
 * rectangle shows chart, value, and period labels": "gráfico chico de
 * períodos a la derecha"). Fixed small footprint, no axes/grid/tooltip —
 * just the trend line for the metric's period series.
 *
 * Color (spec "Sparkline Color by Direction", U2): reuses Pantalla A's
 * `text-state-good/bad/flat` + `currentColor` mapping (see
 * `components/metrics/SparkLine.tsx`) when `estado` is known. `estado`
 * is `null` whenever the metric's `direccion` isn't declared (see
 * `lib/semantics.ts::evaluarMetricaCalculada`) — in that case the line
 * stays the original neutral blue (`#2563eb`), never green/red, since a
 * direction was never confirmed for those KPIs.
 */
const ESTADO_STROKE_CLASS: Record<EstadoMetrica, string> = {
  good: "text-state-good",
  bad: "text-state-bad",
  flat: "text-state-flat",
};

const COLOR_NEUTRO = "#2563eb";

export function Sparkline({ serie, estado }: { serie: Record<string, number>; estado: EstadoMetrica | null }) {
  const data = Object.entries(serie).map(([periodo, valor]) => ({ periodo, valor }));
  const claseColor = estado ? ESTADO_STROKE_CLASS[estado] : "";
  const stroke = estado ? "currentColor" : COLOR_NEUTRO;

  return (
    <div className={`h-12 w-20 shrink-0 ${claseColor}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="valor"
            stroke={stroke}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
