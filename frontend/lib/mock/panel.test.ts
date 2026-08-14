import { describe, expect, it } from "vitest";
import { MOCK_METRICAS } from "./panel";

function porSlug(slug: string) {
  const metrica = MOCK_METRICAS.find((m) => m.slug === slug);
  if (!metrica) {
    throw new Error(`fixture not found for slug: ${slug}`);
  }
  return metrica;
}

describe("MOCK_METRICAS objetivo honesty (kpi_id mapping vs. BENCHMARKS_AR)", () => {
  it("consultas-nuevas (kpi_id 1, BENCHMARKS_AR sin_benchmark) → objetivo null", () => {
    expect(porSlug("consultas-nuevas").objetivo).toBeNull();
  });

  it("horas-tareas-repetitivas (kpi_id 15, proxy_internacional sin rango numérico) → objetivo null", () => {
    expect(porSlug("horas-tareas-repetitivas").objetivo).toBeNull();
  });

  it("produccion-hora-sillon (kpi_id 12, proxy_internacional sin rango numérico) → objetivo null", () => {
    expect(porSlug("produccion-hora-sillon").objetivo).toBeNull();
  });

  it("tasa-no-show (kpi_id 4, consultora_ar con rango real) → objetivo numérico", () => {
    expect(porSlug("tasa-no-show").objetivo).toBe(12);
  });

  it("tasa-reactivacion (kpi_id 9, proxy_internacional con rango real) → objetivo numérico", () => {
    expect(porSlug("tasa-reactivacion").objetivo).toBe(25);
  });

  it("tasa-aceptacion-presupuestos (kpi_id 5, proxy_internacional con rango real) → objetivo numérico", () => {
    expect(porSlug("tasa-aceptacion-presupuestos").objetivo).toBe(65);
  });
});
