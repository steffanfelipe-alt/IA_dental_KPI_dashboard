"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Panel } from "@/components/ui/Panel";
import { InformeText } from "@/components/veredicto/InformeText";
import type { DiagnosticoResponse, EstadoEvidencia, InformeResponse } from "@/lib/types/api";

/**
 * components/veredicto/DiagnosticoView.tsx
 *
 * Diagnóstico section (design "DiagnosticoView: informe report + chart +
 * strengths/weaknesses summary box"): the LLM narrative (`InformeText`), a
 * chart showing how many `Diagnostico` entries fall in each
 * `EstadoEvidencia` bucket, and a fuertes/débiles summary box derived from
 * `diagnostico.diagnostico` (HEALTHY/NORMAL = fuerte, WATCH/PROBLEM/
 * CRITICAL = débil; INSUFFICIENT_EVIDENCE counts in the chart only, it is
 * neither).
 *
 * JUDGMENT CALL (design "Open Questions" left the chart type unspecified):
 * a horizontal bar of estado counts communicates the overall health
 * distribution at a glance. `Sparkline`/`PeriodChart` (Phase 3) are shaped
 * for a single metric's series over time, not a categorical count across
 * the whole diagnóstico — a bar chart fits this data shape better than
 * reusing those.
 */

const ESTADO_ORDER: EstadoEvidencia[] = ["CRITICAL", "PROBLEM", "WATCH", "INSUFFICIENT_EVIDENCE", "NORMAL", "HEALTHY"];

const ESTADO_LABEL: Record<EstadoEvidencia, string> = {
  CRITICAL: "Crítico",
  PROBLEM: "Problema",
  WATCH: "A vigilar",
  INSUFFICIENT_EVIDENCE: "Evidencia insuficiente",
  NORMAL: "Normal",
  HEALTHY: "Saludable",
};

const ESTADO_COLOR: Record<EstadoEvidencia, string> = {
  CRITICAL: "#dc2626",
  PROBLEM: "#ea580c",
  WATCH: "#d97706",
  INSUFFICIENT_EVIDENCE: "#94a3b8",
  NORMAL: "#64748b",
  HEALTHY: "#16a34a",
};

const FUERTE_ESTADOS: EstadoEvidencia[] = ["HEALTHY", "NORMAL"];
const DEBIL_ESTADOS: EstadoEvidencia[] = ["WATCH", "PROBLEM", "CRITICAL"];

export function DiagnosticoView({
  diagnostico,
  informe,
}: {
  diagnostico: DiagnosticoResponse;
  informe: InformeResponse;
}) {
  const items = diagnostico.diagnostico;
  const data = ESTADO_ORDER.map((estado) => ({
    estado,
    label: ESTADO_LABEL[estado],
    cantidad: items.filter((item) => item.estado === estado).length,
  })).filter((row) => row.cantidad > 0);

  const fuertes = items.filter((item) => FUERTE_ESTADOS.includes(item.estado));
  const debiles = items.filter((item) => DEBIL_ESTADOS.includes(item.estado));

  return (
    <div className="flex flex-col gap-6">
      <Panel>
        <h2 className="text-lg font-semibold text-ink-900">Informe</h2>
        <div className="mt-4">
          <InformeText texto={informe.texto} />
        </div>
      </Panel>

      <Panel>
        <h2 className="text-lg font-semibold text-ink-900">Distribución de hallazgos por estado</h2>
        <div className="mt-4 h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e7eb" />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: "#6b7280" }} />
              <YAxis
                type="category"
                dataKey="label"
                width={140}
                tickLine={false}
                axisLine={{ stroke: "#e5e7eb" }}
                tick={{ fontSize: 12, fill: "#6b7280" }}
              />
              <Bar dataKey="cantidad" isAnimationActive={false}>
                {data.map((row) => (
                  <Cell key={row.estado} fill={ESTADO_COLOR[row.estado]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="grid gap-4 sm:grid-cols-2">
        <Panel>
          <h3 className="text-sm font-semibold text-ink-900">Fortalezas ({fuertes.length})</h3>
          {fuertes.length > 0 ? (
            <ul className="mt-3 flex flex-col gap-2 text-sm text-ink-600">
              {fuertes.map((item) => (
                <li key={item.kpi_id}>{item.problema}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-ink-600">Sin hallazgos saludables todavía.</p>
          )}
        </Panel>
        <Panel>
          <h3 className="text-sm font-semibold text-ink-900">Puntos débiles ({debiles.length})</h3>
          {debiles.length > 0 ? (
            <ul className="mt-3 flex flex-col gap-2 text-sm text-ink-600">
              {debiles.map((item) => (
                <li key={item.kpi_id}>{item.problema}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-ink-600">Sin puntos débiles detectados.</p>
          )}
        </Panel>
      </div>
    </div>
  );
}
