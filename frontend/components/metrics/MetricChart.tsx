"use client";

import { Line, LineChart, ResponsiveContainer, XAxis } from "recharts";
import type { PuntoSerie } from "@/lib/types";

/**
 * components/metrics/MetricChart.tsx
 *
 * Pantalla D's full-size chart (SPEC "Pantalla D — Metric Detail": "un
 * `MetricChart` completo con el segmento proyectado punteado y
 * legendeado `Proyección`, nunca fusionado con los datos reales").
 * Same recharts primitive family as `SparkLine.tsx` (axis-less small
 * chart) and `veredicto/PeriodChart.tsx` (large chart w/ `XAxis`), but
 * this is the first chart in the codebase that renders TWO series on
 * one line — real (solid) and projected (dashed) — without ever letting
 * them blend into a single continuous stroke.
 *
 * The trick: split `serie` into two parallel dataKeys, `valorReal` and
 * `valorProyectado`, both `null` where they don't apply. Recharts leaves
 * a gap wherever a dataKey is `null` (`connectNulls={false}`), so the
 * two `<Line>`s never draw over each other — EXCEPT at the exact
 * boundary point (the last real point right before the first projected
 * one), which is deliberately duplicated into `valorProyectado` too, so
 * the dashed segment starts exactly where the solid one ends instead of
 * leaving a visible gap between "real" and "proyectado".
 *
 * The legend itself is plain markup, not recharts' `<Legend>` — every
 * other chart in this codebase (`SparkLine`, `PeriodChart`) keeps
 * anything that needs to be reliably testable/accessible outside the
 * recharts SVG (see `MetricCard`'s "Serie insuficiente" fallback for the
 * same pattern), and `<Legend>` would need its own jsdom mock plumbing
 * for no real benefit here.
 */
interface PuntoChart {
  periodo: string;
  valorReal: number | null;
  valorProyectado: number | null;
}

export function construirDatosChart(serie: PuntoSerie[]): PuntoChart[] {
  return serie.map((punto, indice) => {
    const siguienteEsProyectado = serie[indice + 1]?.proyectado === true;
    const esPuenteHaciaProyeccion = !punto.proyectado && siguienteEsProyectado;
    return {
      periodo: punto.periodo,
      valorReal: punto.proyectado ? null : punto.valor,
      valorProyectado: punto.proyectado || esPuenteHaciaProyeccion ? punto.valor : null,
    };
  });
}

export function MetricChart({ serie }: { serie: PuntoSerie[] }) {
  const datos = construirDatosChart(serie);
  const tieneProyeccion = serie.some((punto) => punto.proyectado);

  return (
    <div>
      <div className="h-72 w-full text-primary-600">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={datos} margin={{ top: 16, right: 16, left: 8, bottom: 8 }}>
            <XAxis dataKey="periodo" tickLine={false} axisLine={{ stroke: "#e3e8ef" }} tick={{ fontSize: 12, fill: "#7a8797" }} />
            <Line
              type="monotone"
              dataKey="valorReal"
              name="Real"
              stroke="currentColor"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="valorProyectado"
              name="Proyección"
              stroke="currentColor"
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={{ r: 3 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {tieneProyeccion ? (
        <div className="mt-2 flex items-center gap-4 text-xs text-text-muted">
          <span className="flex items-center gap-1.5">
            <span aria-hidden="true" className="h-0.5 w-4 bg-current" />
            Real
          </span>
          <span className="flex items-center gap-1.5">
            <span aria-hidden="true" className="h-0.5 w-4 border-t-2 border-dashed border-current" />
            Proyección
          </span>
        </div>
      ) : null}
    </div>
  );
}
