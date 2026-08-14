import Link from "next/link";
import { notFound } from "next/navigation";
import { getSistema } from "@/lib/data/sistemas";
import { resolverClinicaIdActual } from "@/lib/session";
import { resolveSistemaBreadcrumb } from "@/lib/nav";
import { formatearNumero } from "@/lib/format";
import { MetricCard } from "@/components/metrics/MetricCard";
import { AnchorButton } from "@/components/systems/AnchorButton";
import { StepsPanel } from "@/components/systems/StepsPanel";
import { SystemStatusChip } from "@/components/systems/SystemStatusChip";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";

/**
 * app/(app)/(dashboard)/sistemas/[slug]/page.tsx
 *
 * Pantalla C (SPEC "Pantalla C — System Detail"): the SINGLE
 * implementation for every entry point, `?from=panel|catalogo` only
 * changes the breadcrumb (SPEC hard rule; design's "System detail"
 * decision explicitly rejected "duplicate view per entry"). Left column
 * is `StepsPanel` (steps+dependencies+credentials together, task
 * 6.1–6.4); the right side is this system's associated metric cards in a
 * responsive 2→4 column grid (task 6.5), reusing `MetricCard` unchanged —
 * `Sistema.metricas` is `MetricaConObjetivoSistema[]`, which structurally
 * satisfies `MetricCard`'s `Metrica` prop.
 *
 * `?from=metrica` is a THIRD value `ActionsTable` (PR3, Pantalla D)
 * already emits ahead of this page existing — SPEC's own Pantalla C text
 * only documents `panel|catalogo`. `ActionsTable`'s link carries no
 * source-metric slug, so there's no way to build an exact "back to that
 * metric" href; falls back to the catalog breadcrumb target below. Not
 * resolved by SPEC — flagged in this PR's apply-progress as an open item
 * for Felipe, not silently invented.
 *
 * Same `clinicaId`-from-session invariant as `panel/page.tsx` and
 * `metricas/[slug]/page.tsx`: NEVER from `params`/`searchParams`, even
 * though `slug` itself IS a route param — it identifies the system being
 * viewed, not the tenant.
 *
 * Breadcrumb resolution moved to `lib/nav.ts::resolveSistemaBreadcrumb`
 * in PR5 — see that function's header for why (testability) and that the
 * mapping itself is unchanged from PR4.
 *
 * Task 5.4: `AnchorButton` sits next to `SystemStatusChip` here — the
 * THIRD anchor entry point (with `/panel`'s `SystemsBlock` and
 * `/sistemas`'s catalog tiles), all three sharing `AnclajeContext`. No
 * `AnclajeSeed` call here: a single system's slug is never a correct
 * first-run seed for the whole store, so seeding stays on the two pages
 * that see the full list.
 */
export default async function SistemaDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { slug } = await params;
  const query = await searchParams;
  const fromParam = query.from;
  const from = typeof fromParam === "string" ? fromParam : undefined;
  const breadcrumb = resolveSistemaBreadcrumb(from);

  let sistema;
  try {
    const clinicaId = await resolverClinicaIdActual();
    sistema = await getSistema(clinicaId, slug);
  } catch {
    return (
      <div className="p-8">
        <ErrorState title="No pudimos cargar el sistema" />
      </div>
    );
  }

  if (!sistema) {
    notFound();
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-col gap-3 border-b border-border-subtle p-8 pb-6">
        <nav aria-label="Volver">
          <Link href={breadcrumb.href} className="text-sm text-text-muted hover:text-text-body hover:underline">
            ← {breadcrumb.label}
          </Link>
        </nav>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-text-strong">{sistema.nombre}</h1>
          <SystemStatusChip estado={sistema.estado} />
          <span className="text-xs tabular-nums text-text-muted">{formatearNumero(sistema.progresoPct)}% completado</span>
          <AnchorButton sistema={sistema} />
        </div>
        <p className="max-w-2xl text-sm text-text-muted">{sistema.descripcionCorta}</p>
      </div>

      <div className="flex flex-1 flex-col md:flex-row">
        <StepsPanel pasos={sistema.pasos} dependencias={sistema.dependencias} credenciales={sistema.credenciales} />

        <div className="flex-1 p-8">
          <h2 className="mb-3 text-lg font-semibold text-text-strong">Métricas asociadas</h2>
          {sistema.metricas.length === 0 ? (
            <EmptyState title="Este sistema todavía no tiene métricas asociadas." />
          ) : (
            <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
              {sistema.metricas.map((metrica) => (
                <MetricCard key={metrica.slug} metrica={metrica} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
