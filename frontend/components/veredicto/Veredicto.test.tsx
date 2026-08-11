// @vitest-environment jsdom
import { describe, expect, it, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { Veredicto } from "./Veredicto";
import type { DiagnosticoResponse, InformeResponse } from "@/lib/types/api";
import type { MetricaCalculada } from "@/lib/types/metricas";

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
  },
];

/**
 * Task 2.6: render `Veredicto`, click each nav item, assert active
 * section swaps. Follows this repo's manual `afterEach(cleanup)`
 * convention (`GuiaForm.test.tsx`) — no global RTL auto-cleanup exists.
 */
describe("Veredicto (task 2.6)", () => {
  afterEach(cleanup);

  it("starts on the Métricas section", () => {
    render(<Veredicto diagnostico={diagnostico} informe={informe} metricas={metricas} />);

    expect(screen.getByText(/Sección Métricas/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Métricas/ }).getAttribute("aria-current")).toBe("true");
  });

  it("switches to Diagnóstico when its nav item is clicked", () => {
    render(<Veredicto diagnostico={diagnostico} informe={informe} metricas={metricas} />);

    fireEvent.click(screen.getByRole("button", { name: /Diagnóstico/ }));

    expect(screen.getByText(/Sección Diagnóstico/)).toBeTruthy();
    expect(screen.queryByText(/Sección Métricas/)).toBeNull();
    expect(screen.getByRole("button", { name: /Diagnóstico/ }).getAttribute("aria-current")).toBe("true");
  });

  it("switches to Próximos pasos when its nav item is clicked", () => {
    render(<Veredicto diagnostico={diagnostico} informe={informe} metricas={metricas} />);

    fireEvent.click(screen.getByRole("button", { name: /Próximos pasos/ }));

    expect(screen.getByText(/Sección Próximos pasos/)).toBeTruthy();
    expect(screen.queryByText(/Sección Diagnóstico/)).toBeNull();
    expect(screen.getByRole("button", { name: /Próximos pasos/ }).getAttribute("aria-current")).toBe("true");
  });
});
