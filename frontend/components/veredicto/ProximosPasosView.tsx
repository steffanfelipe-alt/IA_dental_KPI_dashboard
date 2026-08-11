"use client";

import { Panel } from "@/components/ui/Panel";
import type { Diagnostico, DiagnosticoResponse, EstadoEvidencia } from "@/lib/types/api";

/**
 * components/veredicto/ProximosPasosView.tsx
 *
 * Próximos pasos section (design "ProximosPasosView: weak points paired
 * with improvements, layout parallel to Diagnóstico"): reuses the same
 * WATCH/PROBLEM/CRITICAL weak-point set as `DiagnosticoView`'s "Puntos
 * débiles" box, but pairs each one with a concrete suggested action
 * instead of just naming the problem.
 *
 * JUDGMENT CALL: `Diagnostico` (real backend shape, `parser/diagnostico/
 * diagnostico.py`) has no dedicated "mejora"/"acción sugerida" field. The
 * suggested action is derived from the item's first (highest-priority)
 * `hipotesis[].causa_probable` — addressing the probable cause is the
 * natural next step. When a weak point has no hypothesis yet,
 * `informacion_faltante` is shown instead as the concrete next step
 * (gather that data before acting).
 */

const DEBIL_ESTADOS: EstadoEvidencia[] = ["WATCH", "PROBLEM", "CRITICAL"];

const ESTADO_LABEL: Record<EstadoEvidencia, string> = {
  CRITICAL: "Crítico",
  PROBLEM: "Problema",
  WATCH: "A vigilar",
  INSUFFICIENT_EVIDENCE: "Evidencia insuficiente",
  NORMAL: "Normal",
  HEALTHY: "Saludable",
};

export function ProximosPasosView({ diagnostico }: { diagnostico: DiagnosticoResponse }) {
  const debiles = diagnostico.diagnostico.filter((item) => DEBIL_ESTADOS.includes(item.estado));

  return (
    <div className="flex flex-col gap-6">
      <Panel>
        <h2 className="text-lg font-semibold text-ink-900">Próximos pasos sugeridos</h2>
        <p className="mt-1 text-sm text-ink-600">
          Cada punto débil detectado, junto con la mejora recomendada para resolverlo.
        </p>
      </Panel>

      {debiles.length > 0 ? (
        <div className="flex flex-col gap-4">
          {debiles.map((item) => (
            <Panel key={item.kpi_id} className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-xs font-medium tracking-wide text-ink-400 uppercase">
                  {ESTADO_LABEL[item.estado]}
                </p>
                <h3 className="mt-1 text-base font-semibold text-ink-900">{item.problema}</h3>
              </div>
              <div>
                <p className="text-xs font-medium tracking-wide text-ink-400 uppercase">Mejora sugerida</p>
                <p className="mt-1 text-sm text-ink-600">{mejoraTexto(item)}</p>
              </div>
            </Panel>
          ))}
        </div>
      ) : (
        <Panel>
          <p className="text-sm text-ink-600">No se detectaron puntos débiles para priorizar.</p>
        </Panel>
      )}
    </div>
  );
}

function mejoraTexto(item: Diagnostico): string {
  if (item.hipotesis.length > 0) {
    return `Atender la causa probable: ${item.hipotesis[0].causa_probable}.`;
  }
  if (item.informacion_faltante.length > 0) {
    return `Reunir más información antes de actuar: ${item.informacion_faltante.join(", ")}.`;
  }
  return "Revisar este hallazgo con el equipo para definir una acción concreta.";
}
