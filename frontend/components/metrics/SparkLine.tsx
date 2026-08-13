"use client";

import { Line, LineChart, ResponsiveContainer } from "recharts";
import type { PuntoSerie } from "@/lib/types";
import type { EstadoMetrica } from "@/lib/semantics";

/**
 * components/metrics/SparkLine.tsx
 *
 * Small, axis-less line chart for a `MetricCard` — same shape as
 * `components/veredicto/Sparkline.tsx` (recharts, no axes/grid/tooltip),
 * but takes the SPEC §10 `PuntoSerie[]` shape and colors the line by the
 * metric's `EstadoMetrica` (`lib/semantics.ts::evaluarMetrica`) instead
 * of a fixed blue — the trend line itself should read good/bad/flat at a
 * glance, same as the wireframe's colored sparklines. Uses the `sys-*`/
 * `state-*` token via `currentColor` + a `text-state-*` class (same
 * pattern as `components/shell/Sidebar.tsx`'s inline SVGs), not a
 * hardcoded hex, so it stays in sync with `globals.css`.
 *
 * `MetricCard` only renders this when the series has at least 2 points
 * (see that file's `SERIE_MINIMA_PARA_GRAFICO`) — this component doesn't
 * re-check that itself, it trusts its caller.
 */
const ESTADO_STROKE_CLASS: Record<EstadoMetrica, string> = {
  good: "text-state-good",
  bad: "text-state-bad",
  flat: "text-state-flat",
};

export function SparkLine({ serie, estado }: { serie: PuntoSerie[]; estado: EstadoMetrica }) {
  const data = serie.map((punto) => ({ periodo: punto.periodo, valor: punto.valor }));

  return (
    <div className={`h-12 w-20 shrink-0 ${ESTADO_STROKE_CLASS[estado]}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line type="monotone" dataKey="valor" stroke="currentColor" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
