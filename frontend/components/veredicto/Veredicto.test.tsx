// @vitest-environment jsdom
import { describe, expect, it, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { Veredicto } from "./Veredicto";
import type { DiagnosticoResponse, InformeResponse } from "@/lib/types/api";
import type { MetricaCalculada } from "@/lib/types/metricas";

/**
 * `ResponsiveContainer` measures 0x0 in jsdom (design doc gotcha), so the
 * Métricas grid/detail (Phase 3, `LineChart`) and the Diagnóstico estado
 * distribution chart (Phase 4, `BarChart`) render through a mocked
 * `recharts` module here — these tests assert DOM/state structure, not
 * chart SVG.
 */
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Line: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Bar: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  LabelList: () => null,
  Cell: () => null,
}));

const diagnostico: DiagnosticoResponse = {
  diagnostico: [
    {
      kpi_id: 4,
      problema: "Tasa de no-show",
      estado: "PROBLEM",
      hechos: [],
      anomalias: [],
      hipotesis: [],
      contradicciones: [],
      patrones_cruzados: [],
      informacion_faltante: [],
      confianza: 0.8,
      prioridad: 1,
    },
  ],
};

const informe: InformeResponse = { texto: "# Resumen\n\nTexto de prueba." };

const metricas: MetricaCalculada[] = [
  {
    kpi_id: 4,
    nombre: "Tasa de no-show",
    valor: 18.9,
    unidad: "%",
    confianza: 0.9,
    fuentes: ["planilla_turnos.xlsx"],
    serie: { "2026-01": 22.0, "2026-02": 18.9 },
    agregados: { promedio: 20.45, mediana: 20.45, ultimo: 18.9 },
    direccion: "menor_mejor",
  },
];

/**
 * Task 2.6: render `Veredicto`, click each nav item, assert active
 * section swaps. Follows this repo's manual `afterEach(cleanup)`
 * convention (`GuiaForm.test.tsx`) — no global RTL auto-cleanup exists.
 */
describe("Veredicto (task 2.6)", () => {
  afterEach(cleanup);

  it("starts on the Métricas section, rendering the grid", () => {
    render(<Veredicto diagnostico={diagnostico} informe={informe} metricas={metricas} />);

    expect(screen.getByRole("button", { name: /Tasa de no-show/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Métricas$/ }).getAttribute("aria-current")).toBe("true");
  });

  it("switches to Diagnóstico when its nav item is clicked, rendering the real DiagnosticoView", () => {
    render(<Veredicto diagnostico={diagnostico} informe={informe} metricas={metricas} />);

    fireEvent.click(screen.getByRole("button", { name: /Diagnóstico/ }));

    expect(screen.getByRole("heading", { name: "Resumen" })).toBeTruthy();
    expect(screen.getByText("Texto de prueba.")).toBeTruthy();
    expect(screen.getByText(/Puntos débiles \(1\)/)).toBeTruthy();
    expect(screen.getByText("Tasa de no-show")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Tasa de no-show/ })).toBeNull();
    expect(screen.getByRole("button", { name: /Diagnóstico/ }).getAttribute("aria-current")).toBe("true");
  });

  it("switches to Próximos pasos when its nav item is clicked, rendering the real ProximosPasosView", () => {
    render(<Veredicto diagnostico={diagnostico} informe={informe} metricas={metricas} />);

    fireEvent.click(screen.getByRole("button", { name: /Próximos pasos/ }));

    expect(screen.getByRole("heading", { name: "Próximos pasos sugeridos" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Tasa de no-show" })).toBeTruthy();
    expect(screen.getByText(/Revisar este hallazgo con el equipo/)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Resumen" })).toBeNull();
    expect(screen.getByRole("button", { name: /Próximos pasos/ }).getAttribute("aria-current")).toBe("true");
  });
});

/**
 * Task 3.6/3.7: clicking a Métricas card sets `selectedKpiId`, rendering
 * `MetricDetail` in place of the grid; the back control clears it and
 * restores the grid.
 */
describe("Veredicto Métricas drill-down (task 3.6/3.7)", () => {
  afterEach(cleanup);

  it("opens MetricDetail on card click, and restores the grid on back", () => {
    render(<Veredicto diagnostico={diagnostico} informe={informe} metricas={metricas} />);

    fireEvent.click(screen.getByRole("button", { name: /Tasa de no-show/ }));

    expect(screen.getByRole("heading", { name: "Tasa de no-show" })).toBeTruthy();
    expect(screen.getByText(/Importancia de la métrica/)).toBeTruthy();
    expect(screen.getByText(/Devolución/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Tasa de no-show$/ })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /Volver a la grilla/ }));

    expect(screen.getByRole("button", { name: /Tasa de no-show/ })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Tasa de no-show" })).toBeNull();
  });
});
