import { notFound } from "next/navigation";
import { getMetrica } from "@/lib/data/metricas";
import { resolverClinicaIdActual } from "@/lib/session";
import { evaluarMetrica } from "@/lib/semantics";
import { TrendValue } from "@/components/metrics/TrendValue";
import { TargetBar } from "@/components/metrics/TargetBar";
import { MetricChart } from "@/components/metrics/MetricChart";
import { ActionsTable } from "@/components/systems/ActionsTable";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { ErrorState } from "@/components/ui/ErrorState";

/**
 * app/(app)/(dashboard)/metricas/[slug]/page.tsx
 *
 * Pantalla D (SPEC "Pantalla D — Metric Detail"): hero value+objective,
 * a full `MetricChart` (real vs. `Proyección`, task 5.1), and an
 * `ActionsTable` (task 5.2) — the first real caller of
 * `lib/data/metricas.ts::getMetrica`, which already returns the exact
 * `{ metrica, acciones }` shape this page needs (that loader predates
 * this PR — see its own header for the SPEC §10 endpoint it models).
 *
 * Same `clinicaId`-from-session invariant as `panel/page.tsx`: NEVER
 * from `params`/`searchParams`, even though `slug` itself IS a route
 * param here — that's fine, `slug` identifies the metric being viewed,
 * not the tenant.
 */
export default async function MetricaDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  let datos;
  try {
    const clinicaId = await resolverClinicaIdActual();
    datos = await getMetrica(clinicaId, slug);
  } catch {
    return (
      <div className="p-8">
        <ErrorState title="No pudimos cargar la métrica" />
      </div>
    );
  }

  if (!datos) {
    notFound();
  }

  const { metrica, acciones } = datos;
  const evaluacion = evaluarMetrica(metrica);
  const mostrarTargetBar = metrica.objetivo !== null && evaluacion.avanceHaciaObjetivo !== null;

  return (
    <div className="flex flex-col gap-8 p-8">
      <div>
        <p className="text-sm text-text-muted">{metrica.tipo}</p>
        <h1 className="text-2xl font-semibold text-text-strong">{metrica.nombre}</h1>
        <p className="mt-1 max-w-2xl text-sm text-text-muted">{metrica.definicion}</p>
      </div>

      <div className="max-w-sm">
        <TrendValue
          valorActual={metrica.valorActual}
          valorAnterior={metrica.valorAnterior}
          unidad={metrica.unidad}
          estado={evaluacion.estado}
        />
        {mostrarTargetBar ? (
          <div className="mt-3">
            <TargetBar
              avanceHaciaObjetivo={evaluacion.avanceHaciaObjetivo as number}
              objetivo={metrica.objetivo as number}
              unidad={metrica.unidad}
              estado={evaluacion.estado}
            />
          </div>
        ) : null}
      </div>

      <section>
        <SectionHeading title="Evolución" subtitle={metrica.porQueImporta} />
        <MetricChart serie={metrica.serie} />
      </section>

      <section>
        <SectionHeading title="Acciones que impactarían esta métrica" />
        <ActionsTable acciones={acciones} />
      </section>
    </div>
  );
}
