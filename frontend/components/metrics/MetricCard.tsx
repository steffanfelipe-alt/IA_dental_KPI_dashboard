import Link from "next/link";
import type { Metrica } from "@/lib/types";
import { evaluarMetrica } from "@/lib/semantics";
import { SparkLine } from "./SparkLine";
import { TrendValue } from "./TrendValue";
import { TargetBar } from "./TargetBar";

/**
 * components/metrics/MetricCard.tsx
 *
 * SPEC "Pantalla A": "`MetricCard` MUST be a single click target." — the
 * whole card IS the `<a>` (via `next/link`, navigating to Pantalla D,
 * PR3's `/metricas/[slug]`), not a wrapper with nested clickable pieces.
 * A server component (unlike `veredicto/MetricCard.tsx`, which is a
 * client component because it takes an `onClick` prop for an in-page
 * fullscreen toggle) — this one only navigates, so no client boundary is
 * needed here; only `SparkLine` (recharts) is a client leaf underneath.
 *
 * Color always comes from `lib/semantics.ts::evaluarMetrica` — no other
 * file decides good/bad/flat (SPEC "Metric Semantics").
 */

/**
 * SPEC §11.2 "Serie insuficiente": a trend line needs at least 2 points
 * to mean anything. Below that, show the value with a text fallback
 * instead of a single dangling dot pretending to be a chart.
 */
const SERIE_MINIMA_PARA_GRAFICO = 2;

export function MetricCard({ metrica }: { metrica: Metrica }) {
  const evaluacion = evaluarMetrica(metrica);
  const serieSuficiente = metrica.serie.length >= SERIE_MINIMA_PARA_GRAFICO;
  const mostrarTargetBar = metrica.objetivo !== null && evaluacion.avanceHaciaObjetivo !== null;

  return (
    <Link
      href={`/metricas/${metrica.slug}`}
      className="flex h-full w-full flex-col justify-between gap-3 rounded-2xl border border-border-subtle bg-surface p-4 text-left shadow-sm transition-shadow hover:shadow-md focus:outline-none focus:ring-2 focus:ring-primary-100"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-text-muted">{metrica.nombre}</p>
          <TrendValue
            valorActual={metrica.valorActual}
            valorAnterior={metrica.valorAnterior}
            unidad={metrica.unidad}
            estado={evaluacion.estado}
          />
        </div>
        {serieSuficiente ? (
          <SparkLine serie={metrica.serie} estado={evaluacion.estado} />
        ) : (
          <span className="shrink-0 text-xs text-text-muted">Serie insuficiente</span>
        )}
      </div>

      {mostrarTargetBar ? (
        <TargetBar
          avanceHaciaObjetivo={evaluacion.avanceHaciaObjetivo as number}
          objetivo={metrica.objetivo as number}
          unidad={metrica.unidad}
          estado={evaluacion.estado}
        />
      ) : null}
    </Link>
  );
}
