"use client";

import { useState } from "react";
import type { DiagnosticoResponse, InformeResponse } from "@/lib/types/api";
import type { MetricaCalculada } from "@/lib/types/metricas";
import { SectionNav, type VeredictoSection } from "@/components/veredicto/SectionNav";
import { MetricasGrid } from "@/components/veredicto/MetricasGrid";
import { MetricDetail } from "@/components/veredicto/MetricDetail";
import { DiagnosticoView } from "@/components/veredicto/DiagnosticoView";
import { ProximosPasosView } from "@/components/veredicto/ProximosPasosView";

/**
 * components/veredicto/Veredicto.tsx
 *
 * Client shell for the veredicto page (design "Section nav + drill-down =
 * local state, not URL routes"): owns which of the 3 sections is active
 * and which metric (if any) is drilled into, both as local `useState` —
 * not nested routes or `?section=` search params, per that design
 * decision. `veredicto/page.tsx` (Server Component) fetches/guards and
 * passes mock data down as props; this component only handles
 * client-side interactivity.
 *
 * All 3 sections now render real views: Métricas via `MetricasGrid`/
 * `MetricCard`/`MetricDetail` (Phase 3), Diagnóstico via `DiagnosticoView`
 * and Próximos pasos via `ProximosPasosView` (both Phase 4, closing out
 * this change).
 */
export function Veredicto({
  diagnostico,
  informe,
  metricas,
}: {
  diagnostico: DiagnosticoResponse;
  informe: InformeResponse;
  metricas: MetricaCalculada[];
}) {
  const [section, setSection] = useState<VeredictoSection>("metricas");
  const [selectedKpiId, setSelectedKpiId] = useState<number | null>(null);

  const metricaSeleccionada =
    selectedKpiId !== null ? (metricas.find((metrica) => metrica.kpi_id === selectedKpiId) ?? null) : null;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold text-ink-900">Veredicto</h1>

      <SectionNav active={section} onChange={setSection} />

      {section === "metricas" ? (
        metricaSeleccionada ? (
          <MetricDetail metrica={metricaSeleccionada} onBack={() => setSelectedKpiId(null)} />
        ) : (
          <MetricasGrid metricas={metricas} onSelect={setSelectedKpiId} />
        )
      ) : null}

      {section === "diagnostico" ? <DiagnosticoView diagnostico={diagnostico} informe={informe} /> : null}

      {section === "proximos" ? <ProximosPasosView diagnostico={diagnostico} /> : null}
    </main>
  );
}
