// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MetricChart, construirDatosChart } from "./MetricChart";
import type { PuntoSerie } from "@/lib/types";

/**
 * `ResponsiveContainer` measures 0x0 in jsdom (same gotcha documented in
 * `MetricCard.test.tsx`) — mock `recharts` and assert on the props each
 * `<Line>` receives instead of rendered SVG output. `XAxis` is mocked
 * away too since it renders nothing test-relevant here.
 */
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  XAxis: () => null,
  Line: ({ dataKey, strokeDasharray }: { dataKey: string; strokeDasharray?: string }) => (
    <div data-testid={`line-${dataKey}`} data-dash={strokeDasharray ?? ""} />
  ),
}));

const SERIE_CON_PROYECCION: PuntoSerie[] = [
  { periodo: "2026-05", valor: 40, proyectado: false },
  { periodo: "2026-06", valor: 45, proyectado: false },
  { periodo: "2026-07", valor: 50, proyectado: true },
  { periodo: "2026-08", valor: 55, proyectado: true },
];

const SERIE_SOLO_REAL: PuntoSerie[] = [
  { periodo: "2026-06", valor: 45, proyectado: false },
  { periodo: "2026-07", valor: 50, proyectado: false },
];

describe("construirDatosChart (task 5.1)", () => {
  it("keeps real points only in valorReal and null in valorProyectado", () => {
    const datos = construirDatosChart(SERIE_CON_PROYECCION);
    expect(datos[0]).toEqual({ periodo: "2026-05", valorReal: 40, valorProyectado: null });
  });

  it("bridges the last real point into valorProyectado so the dashed segment connects with no gap", () => {
    const datos = construirDatosChart(SERIE_CON_PROYECCION);
    // last real point (index 1, valor 45) must appear in BOTH keys
    expect(datos[1]).toEqual({ periodo: "2026-06", valorReal: 45, valorProyectado: 45 });
  });

  it("keeps projected points only in valorProyectado and null in valorReal", () => {
    const datos = construirDatosChart(SERIE_CON_PROYECCION);
    expect(datos[2]).toEqual({ periodo: "2026-07", valorReal: null, valorProyectado: 50 });
    expect(datos[3]).toEqual({ periodo: "2026-08", valorReal: null, valorProyectado: 55 });
  });

  it("never marks a point as projected when the series has no proyectado points", () => {
    const datos = construirDatosChart(SERIE_SOLO_REAL);
    expect(datos.every((punto) => punto.valorProyectado === null)).toBe(true);
  });
});

describe("MetricChart (task 5.1/5.4)", () => {
  afterEach(cleanup);

  it("renders the real line without a dash pattern and the projected line dashed", () => {
    render(<MetricChart serie={SERIE_CON_PROYECCION} />);

    const lineaReal = screen.getByTestId("line-valorReal");
    const lineaProyectada = screen.getByTestId("line-valorProyectado");

    expect(lineaReal.getAttribute("data-dash")).toBe("");
    expect(lineaProyectada.getAttribute("data-dash")).toBe("6 4");
  });

  it("shows the 'Proyección' legend label when the series has projected points", () => {
    render(<MetricChart serie={SERIE_CON_PROYECCION} />);
    expect(screen.getByText("Proyección")).toBeTruthy();
    expect(screen.getByText("Real")).toBeTruthy();
  });

  it("does not show the legend when the series has no projected points", () => {
    render(<MetricChart serie={SERIE_SOLO_REAL} />);
    expect(screen.queryByText("Proyección")).toBeNull();
  });
});
