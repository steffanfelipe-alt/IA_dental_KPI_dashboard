import Link from "next/link";
import type { AccionSobreMetrica } from "@/lib/types";
import { formatearNumero } from "@/lib/format";
import { EmptyState } from "@/components/ui/EmptyState";
import { SystemStatusChip } from "./SystemStatusChip";

/**
 * components/systems/ActionsTable.tsx
 *
 * Pantalla D's action table (SPEC "Pantalla D — Metric Detail": "un
 * `ActionsTable` con `TODO(felpa)` en las columnas exactas; MUST
 * default a `Sistema a implementar | Impacto estimado % | Valor
 * proyectado | Estado`"). Rows link to `/sistemas/[slug]?from=metrica`
 * (SPEC's `?from=panel|catalogo|metrica` breadcrumb convention for
 * Pantalla C — that route ships in PR4; this link is written ahead of
 * it per the tasks artifact's stated PR3→PR4 dependency order, same as
 * `MetricCard` linked to `/metricas/[slug]` a PR before this route
 * existed).
 *
 * TODO(felpa): SPEC §13 open item 1 — "Pantalla D `ActionsTable` exact
 * columns (assumed default above, unconfirmed)." The four columns below
 * are SPEC's own explicit default/fallback text, not an invented guess,
 * but they remain UNCONFIRMED by Felipe — do not add/remove/reorder
 * columns without checking this TODO first.
 */
const COLUMNAS = ["Sistema", "Impacto %", "Valor proyectado", "Estado"] as const;

export function ActionsTable({ acciones }: { acciones: AccionSobreMetrica[] }) {
  if (acciones.length === 0) {
    return <EmptyState title="Todavía no hay acciones sugeridas para esta métrica." />;
  }

  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-border-subtle text-left text-xs font-medium tracking-wide text-text-muted uppercase">
          {COLUMNAS.map((columna) => (
            <th key={columna} scope="col" className="py-2 pr-4 font-medium">
              {columna}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {acciones.map((accion) => (
          <tr key={accion.sistema.slug} className="border-b border-border-subtle last:border-0">
            <td className="py-3 pr-4">
              <Link
                href={`/sistemas/${accion.sistema.slug}?from=metrica`}
                className="font-medium text-text-strong hover:text-primary-600 hover:underline"
              >
                {accion.sistema.nombre}
              </Link>
              <p className="mt-0.5 text-xs text-text-muted">{accion.porQueServiria}</p>
            </td>
            <td className="py-3 pr-4 tabular-nums text-text-body">
              {formatearNumero(accion.impactoEstimadoPct, { maximumFractionDigits: 1 })}%
            </td>
            <td className="py-3 pr-4 tabular-nums text-text-body">{formatearNumero(accion.valorProyectado)}</td>
            <td className="py-3 pr-4">
              <SystemStatusChip estado={accion.sistema.estado} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
