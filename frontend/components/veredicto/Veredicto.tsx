"use client";

import { useState } from "react";
import { Panel } from "@/components/ui/Panel";
import type { DiagnosticoResponse, InformeResponse } from "@/lib/types/api";
import type { MetricaCalculada } from "@/lib/types/metricas";
import { SectionNav, type VeredictoSection } from "@/components/veredicto/SectionNav";
import { MetricasGrid } from "@/components/veredicto/MetricasGrid";
import { MetricDetail } from "@/components/veredicto/MetricDetail";

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
 * Métricas renders the real grid + drill-down (`MetricasGrid`/
 * `MetricCard`/`MetricDetail`, Phase 3). Diagnóstico and Próximos pasos
 * bodies below are still placeholders — `DiagnosticoView` and
 * `ProximosPasosView` are Phase 4 work, out of scope for this PR.
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

      {section === "diagnostico" ? (
        <Panel>
          <p className="text-sm text-ink-600">
            Sección Diagnóstico ({diagnostico.diagnostico.length} hallazgos) — vista en construcción.
          </p>
        </Panel>
      ) : null}

      {section === "proximos" ? (
        <Panel>
          <p className="text-sm text-ink-600">
            Sección Próximos pasos ({informe.texto.length > 0 ? "informe disponible" : "sin informe"}) — vista en
            construcción.
          </p>
        </Panel>
      ) : null}
    </main>
  );
}
