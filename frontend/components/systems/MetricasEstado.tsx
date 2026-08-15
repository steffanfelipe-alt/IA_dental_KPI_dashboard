import Link from "next/link";
import type { MetricaConObjetivoSistema, Sistema } from "@/lib/types";
import { COPY } from "@/lib/copy";
import { formatearNumero } from "@/lib/format";

/**
 * components/systems/MetricasEstado.tsx
 *
 * Slice 2 WU-B2: replaces the `TODO(felpa)` placeholder in
 * `app/(app)/(dashboard)/sistemas/page.tsx`'s "Métricas y estado" section
 * (SPEC "Métricas y Estado — Direct and Indirect Impact"). One instance
 * per system with at least one associated metric — the page maps over
 * the already-fetched `Sistema[]` and renders this once per entry, which
 * is what SPEC's "exhaustive per-system view" wording means (distinct
 * from Pantalla C's `[slug]` detail page, which shows a flat `MetricCard`
 * grid unchanged — this block is `/sistemas`-only, not a replacement for
 * that page).
 *
 * `lib/data/sistemas.ts::getSistemas`/`getSistema` (WU-B1) already
 * compute every metric's `relacion` pass-through and signed `impactoReal`
 * — this component only groups and renders, it never recomputes either.
 *
 * "Not yet measurable" (SPEC "System not yet implemented" scenario) is
 * driven per metric by `impactoReal === null`, not by a separate
 * `sistema.fechaImplementacion` check here: `getSistema`/`getSistemas`
 * already force every metric's `impactoReal` to `null` when the system
 * has no `fechaImplementacion` (see that file's `conVentanaEImpacto`), so
 * checking `impactoReal` alone covers both "system never implemented" and
 * "this one metric has no `valorAlImplementar` anchor" without this
 * component needing to know why.
 *
 * ALL indirect metrics render — no top-N cap (SPEC "Exhaustive indirect
 * listing" scenario, the reason `recordatorios-turnos`'s mock fixture
 * carries 9 indirect associations, WU-B1).
 */
function MetricaImpactoRow({ metrica }: { metrica: MetricaConObjetivoSistema }) {
  const medible = metrica.impactoReal !== null && metrica.impactoReal !== undefined;

  return (
    <li className="rounded-xl border border-border-subtle bg-surface p-3">
      <p className="truncate text-sm font-medium text-text-strong">{metrica.nombre}</p>
      {medible ? (
        <p
          className={`mt-1 text-sm font-semibold tabular-nums ${
            (metrica.impactoReal as number) >= 0 ? "text-state-good" : "text-state-bad"
          }`}
        >
          {(metrica.impactoReal as number) >= 0 ? "+" : ""}
          {formatearNumero(metrica.impactoReal as number, { maximumFractionDigits: 1 })} {metrica.unidad}
        </p>
      ) : (
        <p className="mt-1 text-xs text-text-muted">{COPY.sistemas.metricasYEstado.noImplementadoAun}</p>
      )}
    </li>
  );
}

export function MetricasEstado({ sistema }: { sistema: Sistema }) {
  const directas = sistema.metricas.filter((metrica) => metrica.relacion === "directa");
  const indirectas = sistema.metricas.filter((metrica) => metrica.relacion === "indirecta");

  if (directas.length === 0 && indirectas.length === 0) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-border-subtle bg-surface p-4">
      <Link
        href={`/sistemas/${sistema.slug}?from=catalogo`}
        className="rounded text-sm font-semibold text-text-strong hover:underline focus:outline-none focus:ring-2 focus:ring-primary-100"
      >
        {sistema.nombre}
      </Link>

      {directas.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs font-semibold tracking-wide text-text-muted uppercase">{COPY.sistemas.metricasYEstado.tituloDirectas}</p>
          <ul className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3" role="list">
            {directas.map((metrica) => (
              <MetricaImpactoRow key={metrica.slug} metrica={metrica} />
            ))}
          </ul>
        </div>
      ) : null}

      {indirectas.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs font-semibold tracking-wide text-text-muted uppercase">{COPY.sistemas.metricasYEstado.tituloIndirectas}</p>
          <p className="mt-1 text-xs text-text-muted">{COPY.sistemas.metricasYEstado.disclaimerIndirectas}</p>
          <ul className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3" role="list">
            {indirectas.map((metrica) => (
              <MetricaImpactoRow key={metrica.slug} metrica={metrica} />
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
