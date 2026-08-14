// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MetricasGrid } from "./MetricasGrid";
import type { MetricaCalculada } from "@/lib/types/metricas";

/**
 * `ResponsiveContainer` measures 0x0 in jsdom (same gotcha as
 * `MetricCard.test.tsx`) — mock `recharts` and assert DOM structure.
 */
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
}));

function metrica(kpiId: number): MetricaCalculada {
  return {
    kpi_id: kpiId,
    nombre: `Métrica ${kpiId}`,
    valor: kpiId,
    unidad: "%",
    confianza: 0.9,
    fuentes: ["planilla.xlsx"],
    serie: null,
    agregados: null,
    direccion: null,
  };
}

describe("MetricasGrid (spec veredicto-metrics-layout)", () => {
  afterEach(cleanup);

  it("renders more than 4 metrics in a 4-column grid with no horizontal-scroll container", () => {
    const metricas = Array.from({ length: 21 }, (_, i) => metrica(i + 1));
    const { container } = render(<MetricasGrid metricas={metricas} onSelect={vi.fn()} />);

    const grid = container.firstElementChild as HTMLElement;
    expect(grid.className).toMatch(/\bgrid\b/);
    expect(grid.className).toMatch(/grid-cols-1/);
    expect(grid.className).toMatch(/lg:grid-cols-4/);
    expect(grid.className).not.toMatch(/overflow-x-auto/);

    for (const m of metricas) {
      expect(screen.getByText(m.nombre)).toBeTruthy();
    }
  });

  it("does not stretch cards to a fixed width when fewer than 4 metrics are present", () => {
    const metricas = [metrica(1), metrica(2)];
    render(<MetricasGrid metricas={metricas} onSelect={vi.fn()} />);

    for (const button of screen.getAllByRole("button")) {
      expect(button.className).not.toMatch(/\bw-64\b/);
      expect(button.className).toMatch(/\bw-full\b/);
    }
  });

  it("calls onSelect with the clicked metric's kpi_id", () => {
    const onSelect = vi.fn();
    render(<MetricasGrid metricas={[metrica(4)]} onSelect={onSelect} />);

    screen.getByRole("button").click();

    expect(onSelect).toHaveBeenCalledWith(4);
  });
});
