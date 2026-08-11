"use client";

import { Panel } from "@/components/ui/Panel";
import { PeriodChart } from "@/components/veredicto/PeriodChart";
import type { MetricaCalculada } from "@/lib/types/metricas";

/**
 * components/veredicto/MetricDetail.tsx
 *
 * Fullscreen drill-down for one metric (spec "Metric detail shows chart,
 * per-period numbers, importance, and devolución"): a large chart with
 * each period's explicit value, plus "importancia de la métrica en el
 * sistema" and "devolución" (interpretation/verdict) text, and a back
 * control to return to the grid.
 *
 * JUDGMENT CALL: `MetricaCalculada` (lib/types/metricas.ts, Phase 1) has
 * no dedicated `importancia`/`devolución` field — that invented mock type
 * only carries value/series/aggregates/provenance. Rather than reopen the
 * already-merged Phase 1 mock/type files for two narrative-text fields,
 * both texts are derived here from fields that DO exist (`fuentes`,
 * `confianza`, `serie`, `agregados`): importance describes the metric's
 * data provenance/confidence, devolución describes the trend across the
 * series. Revisit if a real backend ever carries dedicated narrative
 * fields for this.
 *
 * The plain `<dl>` list of period→value pairs below the chart is
 * additional to the chart's own `LabelList` numbers: it keeps "explicit
 * numbers per period" true even when `recharts` is mocked out or its
 * SVG doesn't render (jsdom gotcha, see design doc), and is more
 * accessible than reading numbers off an SVG.
 */
export function MetricDetail({ metrica, onBack }: { metrica: MetricaCalculada; onBack: () => void }) {
  return (
    <Panel className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <button type="button" onClick={onBack} className="text-sm font-medium text-primary-600">
            ← Volver a la grilla
          </button>
          <h2 className="mt-2 text-2xl font-semibold text-ink-900">{metrica.nombre}</h2>
        </div>
        <p className="text-4xl font-semibold text-ink-900">
          <span>{metrica.valor}</span>{" "}
          <span className="text-base font-normal text-ink-600">{metrica.unidad}</span>
        </p>
      </div>

      {metrica.serie ? (
        <>
          <PeriodChart serie={metrica.serie} />
          <dl className="grid grid-cols-3 gap-x-4 gap-y-3 text-sm sm:grid-cols-6">
            {Object.entries(metrica.serie).map(([periodo, valor]) => (
              <div key={periodo}>
                <dt className="text-xs text-ink-600">{periodo}</dt>
                <dd className="font-medium text-ink-900">{valor}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : (
        <p className="text-sm text-ink-600">Esta métrica no tiene una serie temporal disponible.</p>
      )}

      <div className="grid gap-4 border-t border-black/5 pt-6 sm:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold text-ink-900">Importancia de la métrica en el sistema</h3>
          <p className="mt-1 text-sm text-ink-600">{importanciaTexto(metrica)}</p>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-ink-900">Devolución</h3>
          <p className="mt-1 text-sm text-ink-600">{devolucionTexto(metrica)}</p>
        </div>
      </div>
    </Panel>
  );
}

function importanciaTexto(metrica: MetricaCalculada): string {
  const fuentesTexto = metrica.fuentes.length > 0 ? metrica.fuentes.join(", ") : "los datos cargados";
  const confianzaPct = Math.round(metrica.confianza * 100);
  return `Esta métrica se calcula a partir de ${fuentesTexto}, con una confianza del ${confianzaPct}%. Forma parte del conjunto de indicadores que el sistema monitorea para evaluar la salud operativa de la clínica.`;
}

function devolucionTexto(metrica: MetricaCalculada): string {
  if (!metrica.serie || !metrica.agregados) {
    return `El valor actual es ${metrica.valor} ${metrica.unidad}. Esta métrica no tiene una serie temporal disponible para describir su evolución.`;
  }

  const valores = Object.values(metrica.serie);
  const primero = valores[0];
  const ultimo = metrica.agregados.ultimo;
  const tendencia = ultimo > primero ? "en aumento" : ultimo < primero ? "en baja" : "estable";

  return `El valor actual (${ultimo} ${metrica.unidad}) está ${tendencia} respecto al inicio de la serie (${primero} ${metrica.unidad}), con un promedio de ${metrica.agregados.promedio} ${metrica.unidad} en el período analizado.`;
}
