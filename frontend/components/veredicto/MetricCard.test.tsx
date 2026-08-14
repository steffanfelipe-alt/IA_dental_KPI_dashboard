// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MetricCard } from "./MetricCard";
import type { MetricaCalculada } from "@/lib/types/metricas";

/**
 * `ResponsiveContainer` measures 0x0 in jsdom (design doc gotcha) — mock
 * `recharts` and assert DOM/state structure, not chart SVG output.
 */
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
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

describe("MetricCard (task 3.7)", () => {
  afterEach(cleanup);

  it("shows the metric's name, value, and period labels from the fixture", () => {
    render(<MetricCard metrica={metricaConSerie} onClick={vi.fn()} />);

    expect(screen.getByText("Tasa de no-show")).toBeTruthy();
    expect(screen.getByText("18.9")).toBeTruthy();
    expect(screen.getByText("%")).toBeTruthy();
    expect(screen.getByText("2026-01")).toBeTruthy();
    expect(screen.getByText("2026-02")).toBeTruthy();
  });

  it("calls onClick when the card is clicked", () => {
    const onClick = vi.fn();
    render(<MetricCard metrica={metricaConSerie} onClick={onClick} />);

    screen.getByRole("button").click();

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders without a sparkline or period labels when serie is null", () => {
    render(<MetricCard metrica={metricaSinSerie} onClick={vi.fn()} />);

    expect(screen.getByText("68.5")).toBeTruthy();
    expect(screen.getByText("hs/mes")).toBeTruthy();
  });
});
