// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MetricDetail } from "./MetricDetail";
import type { MetricaCalculada } from "@/lib/types/metricas";

/**
 * `ResponsiveContainer` measures 0x0 in jsdom (design doc gotcha) — mock
 * `recharts` and assert DOM/state structure, not chart SVG output.
 */
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Line: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  XAxis: () => null,
  LabelList: () => null,
}));

const metricaConSerie: MetricaCalculada = {
  kpi_id: 4,
  nombre: "Tasa de no-show",
  valor: 18.9,
  unidad: "%",
  confianza: 0.9,
  fuentes: ["planilla_turnos.xlsx"],
  serie: { "2026-01": 22.0, "2026-02": 18.9 },
  agregados: { promedio: 20.45, mediana: 20.45, ultimo: 18.9 },
  direccion: "menor_mejor",
};

const metricaSinSerie: MetricaCalculada = {
  kpi_id: 17,
  nombre: "Horas-persona liberadas / mes",
  valor: 68.5,
  unidad: "hs/mes",
  confianza: 0.65,
  fuentes: ["respuestas_diagnostico"],
  serie: null,
  agregados: null,
  direccion: null,
};

describe("MetricDetail (task 3.7)", () => {
  afterEach(cleanup);

  it("shows explicit per-period numbers plus importancia and devolución text", () => {
    render(<MetricDetail metrica={metricaConSerie} onBack={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Tasa de no-show" })).toBeTruthy();
    expect(screen.getByText(/Importancia de la métrica en el sistema/)).toBeTruthy();
    expect(screen.getByText(/Devolución/)).toBeTruthy();
    expect(screen.getByText("2026-01")).toBeTruthy();
    expect(screen.getByText("22")).toBeTruthy();
    expect(screen.getByText("2026-02")).toBeTruthy();
    expect(screen.getAllByText("18.9").length).toBeGreaterThan(0);
  });

  it("calls onBack when the back control is clicked", () => {
    const onBack = vi.fn();
    render(<MetricDetail metrica={metricaConSerie} onBack={onBack} />);

    fireEvent.click(screen.getByRole("button", { name: /Volver a la grilla/ }));

    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("renders a fallback message when serie is null", () => {
    render(<MetricDetail metrica={metricaSinSerie} onBack={vi.fn()} />);

    expect(screen.getAllByText(/no tiene una serie temporal disponible/).length).toBeGreaterThan(0);
  });
});
