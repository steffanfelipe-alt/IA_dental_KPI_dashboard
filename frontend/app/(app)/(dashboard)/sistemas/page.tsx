import { getSistemas } from "@/lib/data/sistemas";
import { resolverClinicaIdActual } from "@/lib/session";
import { COPY, NIVEL_EMBUDO_LABEL, NIVEL_EMBUDO_ORDEN } from "@/lib/copy";
import { formatearNumero } from "@/lib/format";
import { AGRUPACION_SEARCH_PARAM } from "@/lib/searchParams";
import { ESTADO_LABEL } from "@/components/systems/SystemStatusChip";
import { SystemMedallion } from "@/components/systems/SystemMedallion";
import { MetricTypeFilter, type AgrupacionCatalogo } from "@/components/metrics/MetricTypeFilter";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import type { EstadoSistema, Sistema } from "@/lib/types";

/**
 * app/(app)/(dashboard)/sistemas/page.tsx
 *
 * Pantalla B (SPEC "Pantalla B — Catálogo (partial design)"): replaces
 * the PR1 placeholder that only existed so the sidebar's "Sistemas" link
 * resolved to something real. Unlike Pantalla A, this catalog is
 * EXHAUSTIVE — every system regardless of `estado` (including
 * `disponible`) appears here, since SPEC says this block "is exclusively
 * designed for browsing all systems". First real caller of
 * `getSistemas`.
 *
 * Three sections, top to bottom: (1) panorama counts, (2) a `TODO(felpa)`
 * placeholder for "Métricas y estado" (SPEC scenario "Undefined block
 * placeholder" — no confirmed layout exists, so a visible placeholder
 * ships instead of invented content), (3) the catalog itself, grouped by
 * `nivelEmbudo` (default) or `categoria` via `MetricTypeFilter`'s
 * Embudo/Categoría toggle, `?agrupacion=` shareable by URL like
 * `PeriodPicker`'s `?periodo=` on Pantalla A.
 */
const ESTADO_ORDEN_PANORAMA: EstadoSistema[] = ["implementado", "en_proceso", "sugerido", "disponible"];

interface GrupoCatalogo {
  clave: string;
  label: string;
  items: Sistema[];
}

function agruparPorEmbudo(sistemas: Sistema[]): GrupoCatalogo[] {
  return NIVEL_EMBUDO_ORDEN.map((nivel) => ({
    clave: nivel,
    label: NIVEL_EMBUDO_LABEL[nivel],
    items: sistemas.filter((sistema) => sistema.nivelEmbudo === nivel),
  })).filter((grupo) => grupo.items.length > 0);
}

function agruparPorCategoria(sistemas: Sistema[]): GrupoCatalogo[] {
  const categorias = Array.from(new Set(sistemas.map((sistema) => sistema.categoria))).sort((a, b) => a.localeCompare(b, "es"));
  return categorias.map((categoria) => ({
    clave: categoria,
    label: categoria,
    items: sistemas.filter((sistema) => sistema.categoria === categoria),
  }));
}

export default async function SistemasPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const params = await searchParams;
  const agrupacionParam = params[AGRUPACION_SEARCH_PARAM];
  const agrupacion: AgrupacionCatalogo = agrupacionParam === "categoria" ? "categoria" : "embudo";

  let sistemas: Sistema[];
  try {
    const clinicaId = await resolverClinicaIdActual();
    sistemas = await getSistemas(clinicaId);
  } catch {
    return (
      <div className="p-8">
        <ErrorState title="No pudimos cargar los sistemas" />
      </div>
    );
  }

  const grupos = agrupacion === "categoria" ? agruparPorCategoria(sistemas) : agruparPorEmbudo(sistemas);

  return (
    <div className="flex flex-col gap-8 p-8">
      <h1 className="text-2xl font-semibold text-text-strong">{COPY.sistemas.screenTitle}</h1>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-text-strong">{COPY.sistemas.panoramaTitulo}</h2>
        {sistemas.length === 0 ? (
          <EmptyState title="Todavía no hay sistemas en el catálogo." />
        ) : (
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <div className="rounded-2xl border border-border-subtle bg-surface p-4">
              <dt className="text-xs text-text-muted">{COPY.sistemas.panoramaTotal}</dt>
              <dd className="mt-1 text-2xl font-semibold tabular-nums text-text-strong">{formatearNumero(sistemas.length)}</dd>
            </div>
            {ESTADO_ORDEN_PANORAMA.map((estado) => {
              const cantidad = sistemas.filter((sistema) => sistema.estado === estado).length;
              return (
                <div key={estado} className="rounded-2xl border border-border-subtle bg-surface p-4">
                  <dt className="text-xs text-text-muted">{ESTADO_LABEL[estado]}</dt>
                  <dd className="mt-1 text-2xl font-semibold tabular-nums text-text-strong">{formatearNumero(cantidad)}</dd>
                </div>
              );
            })}
          </dl>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-text-strong">{COPY.sistemas.bloqueMetricasYEstado}</h2>
        <div className="rounded-2xl border border-dashed border-border-subtle bg-surface p-6 text-sm text-text-muted">
          {COPY.sistemas.bloqueMetricasYEstadoTodo}
        </div>
      </section>

      <section>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-text-strong">{COPY.sistemas.bloqueCatalogo}</h2>
          <MetricTypeFilter value={agrupacion} />
        </div>

        {grupos.length === 0 ? (
          <EmptyState title="Todavía no hay sistemas en el catálogo." />
        ) : (
          <div className="flex flex-col gap-6">
            {grupos.map((grupo) => (
              <div key={grupo.clave}>
                <p className="mb-2 text-xs font-semibold tracking-wide text-text-muted uppercase">{grupo.label}</p>
                <ul className="flex flex-wrap gap-4" role="list" aria-label={grupo.label}>
                  {grupo.items.map((sistema) => (
                    <li key={sistema.slug}>
                      <SystemMedallion sistema={sistema} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
