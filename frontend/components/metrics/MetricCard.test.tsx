// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MetricCard } from "./MetricCard";
import type { Metrica } from "@/lib/types";

/**
 * `ResponsiveContainer` measures 0x0 in jsdom (same gotcha documented in
 * `components/veredicto/MetricCard.test.tsx`) — mock `recharts` and
 * assert DOM/state structure, not chart SVG output.
 */
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
}));

function metrica(overrides: Partial<Metrica> = {}): Metrica {
  return {
    slug: "metrica-test",
    nombre: "Métrica de prueba",
    unidad: "%",
    definicion: "definición",
    porQueImporta: "por qué importa",
    tipo: "operacion",
    direccion: "mayor_mejor",
    valorActual: 55,
    valorAnterior: 50,
    objetivo: 70,
    serie: [
      { periodo: "2026-06", valor: 50, proyectado: false },
      { periodo: "2026-07", valor: 55, proyectado: false },
    ],
    impactoScore: 10,
    vulnerabilidadScore: 10,
    sistemasAsociados: [],
    ...overrides,
  };
}

describe("MetricCard (task 3.3/3.4)", () => {
  afterEach(cleanup);

  it("colors the trend good when a mayor_mejor metric improves beyond the 2% threshold", () => {
    const { container } = render(<MetricCard metrica={metrica({ direccion: "mayor_mejor", valorAnterior: 50, valorActual: 55 })} />);
    expect(container.querySelector(".text-state-good")).toBeTruthy();
  });

  it("colors the trend bad when a mayor_mejor metric drops beyond the 2% threshold", () => {
    const { container } = render(<MetricCard metrica={metrica({ direccion: "mayor_mejor", valorAnterior: 55, valorActual: 50 })} />);
    expect(container.querySelector(".text-state-bad")).toBeTruthy();
  });

  it("colors the trend flat when the change is under the 2% threshold", () => {
    const { container } = render(<MetricCard metrica={metrica({ valorAnterior: 50, valorActual: 50.2 })} />);
    expect(container.querySelector(".text-state-flat")).toBeTruthy();
  });

  it("renders a TargetBar with the objetivo and progress when objetivo is set", () => {
    render(<MetricCard metrica={metrica({ objetivo: 70, valorActual: 55 })} />);
    expect(screen.getByRole("progressbar")).toBeTruthy();
    expect(screen.getByText(/objetivo 70/)).toBeTruthy();
  });

  it("does not render a TargetBar when objetivo is null", () => {
    render(<MetricCard metrica={metrica({ objetivo: null })} />);
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("shows 'Serie insuficiente' instead of a sparkline when the series has fewer than 2 points", () => {
    render(<MetricCard metrica={metrica({ serie: [{ periodo: "2026-07", valor: 55, proyectado: false }] })} />);
    expect(screen.getByText("Serie insuficiente")).toBeTruthy();
  });

  it("is a single click target linking to the metric's detail route", () => {
    render(<MetricCard metrica={metrica({ slug: "tasa-no-show" })} />);
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toBe("/metricas/tasa-no-show");
  });
});
