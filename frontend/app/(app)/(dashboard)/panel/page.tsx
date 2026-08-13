import { getPanel } from "@/lib/data/panel";
import { resolverClinicaIdActual } from "@/lib/session";
import { COPY } from "@/lib/copy";
import { PERIODO_SEARCH_PARAM, PeriodPicker, type PeriodoOption } from "@/components/shell/PeriodPicker";
import { MetricCarousel } from "@/components/metrics/MetricCarousel";
import { SystemsBlock } from "@/components/systems/SystemsBlock";
import { ErrorState } from "@/components/ui/ErrorState";

const PERIODO_OPTIONS: PeriodoOption[] = [
  { value: "12m", label: "Últimos 12 meses" },
  { value: "6m", label: "Últimos 6 meses" },
  { value: "3m", label: "Últimos 3 meses" },
];
const PERIODO_DEFAULT = PERIODO_OPTIONS[0].value;

/**
 * app/(app)/(dashboard)/panel/page.tsx
 *
 * Pantalla A (SPEC "Pantalla A — Panel prioritario", design's data flow:
 * `searchParams(periodo) → server page → lib/data/getX() → lib/mock/*`).
 * Replaces the PR1 placeholder — this is the first real caller of
 * `getPanel`, proving the `lib/data/*` loader seam end-to-end (see this
 * PR's description for the hexagonal-architecture note).
 *
 * A1/A2 ordering ("lo calcula el backend" per the wireframe annotation)
 * is a plain `.sort()` here in Slice 1 as a stand-in for that backend
 * computation — `MetricCarousel` itself never sorts, it only renders
 * what it's given (see that component's header).
 */
export default async function PanelPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const params = await searchParams;
  const periodoParam = params[PERIODO_SEARCH_PARAM];
  const periodo = typeof periodoParam === "string" ? periodoParam : PERIODO_DEFAULT;

  let panel;
  try {
    const clinicaId = await resolverClinicaIdActual();
    panel = await getPanel(clinicaId, periodo);
  } catch {
    return (
      <div className="p-8">
        <ErrorState title="No pudimos cargar el panel" />
      </div>
    );
  }

  const metricasPrincipales = [...panel.metricas].sort((a, b) => b.impactoScore - a.impactoScore);
  const metricasCriticas = [...panel.metricas].sort((a, b) => b.vulnerabilidadScore - a.vulnerabilidadScore);

  return (
    <div className="flex flex-col gap-8 p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold text-text-strong">{COPY.panel.screenTitle}</h1>
        <PeriodPicker options={PERIODO_OPTIONS} value={periodo} />
      </div>

      <MetricCarousel titulo={COPY.panel.bloqueMetricasPrincipales} metricas={metricasPrincipales} />
      <MetricCarousel titulo={COPY.panel.bloqueMetricasCriticas} metricas={metricasCriticas} />
      <SystemsBlock sistemas={panel.sistemasEnCurso} />
    </div>
  );
}
