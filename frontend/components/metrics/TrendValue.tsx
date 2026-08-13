import { formatearNumero } from "@/lib/format";
import type { EstadoMetrica } from "@/lib/semantics";

/**
 * components/metrics/TrendValue.tsx
 *
 * The metric's current value plus a small delta indicator (SPEC
 * wireframe: value, unit, and a colored "▲/▼ N%" chip). Two independent
 * signals, deliberately not conflated:
 *   - the ARROW reflects the raw numeric direction (value went up or
 *     down vs. the previous period) — always literal, never
 *     direction-aware;
 *   - the COLOR reflects `estado` (`good|bad|flat` from
 *     `lib/semantics.ts::evaluarMetrica`), which IS direction-aware
 *     (e.g. a drop in "tasa de ausentismo" is colored good even though
 *     the arrow points down).
 * This mirrors the wireframe's own "ausentismo" example (glyph ▼, class
 * `delta up` i.e. favorable/green) — see this PR's tasks-artifact read
 * for the reasoning trail.
 */
const ESTADO_TEXT_CLASS: Record<EstadoMetrica, string> = {
  good: "text-state-good",
  bad: "text-state-bad",
  flat: "text-state-flat",
};

function flechaDelta(deltaPct: number, estado: EstadoMetrica): string {
  if (estado === "flat") return "—";
  return deltaPct > 0 ? "▲" : "▼";
}

interface TrendValueProps {
  valorActual: number;
  valorAnterior: number;
  unidad: string;
  estado: EstadoMetrica;
}

export function TrendValue({ valorActual, valorAnterior, unidad, estado }: TrendValueProps) {
  const base = Math.max(Math.abs(valorAnterior), 1);
  const deltaPct = ((valorActual - valorAnterior) / base) * 100;

  return (
    <p className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
      <span className="text-2xl font-semibold tabular-nums text-text-strong">
        {formatearNumero(valorActual)} <span className="text-sm font-normal text-text-muted">{unidad}</span>
      </span>
      <span className={`text-xs font-medium tabular-nums ${ESTADO_TEXT_CLASS[estado]}`}>
        {flechaDelta(deltaPct, estado)} {formatearNumero(Math.abs(deltaPct), { maximumFractionDigits: 1 })}%
      </span>
    </p>
  );
}
