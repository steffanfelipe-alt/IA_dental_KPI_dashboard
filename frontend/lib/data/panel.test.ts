import { describe, expect, it } from "vitest";
import { getPanel } from "./panel";
import { MOCK_METRICAS } from "@/lib/mock/panel";
import type { Metrica } from "@/lib/types";

const CLINICA_ID = "clinica-test";
const SLUG = "tasa-no-show"; // 24 real points, no `mesesProyectados` noise concern for windowing

function porSlug(metricas: Metrica[], slug: string): Metrica {
  const metrica = metricas.find((m) => m.slug === slug);
  if (!metrica) {
    throw new Error(`fixture not found for slug: ${slug}`);
  }
  return metrica;
}

describe("getPanel — functional period window (Phase 4/U5)", () => {
  it("sin `periodo`, mantiene el comportamiento actual de serie completa (mock's own valorActual/valorAnterior, sin recorte)", async () => {
    const panel = await getPanel(CLINICA_ID);
    const metrica = porSlug(panel.metricas, SLUG);
    const original = porSlug(MOCK_METRICAS, SLUG);

    expect(metrica.valorActual).toBe(original.valorActual);
    expect(metrica.valorAnterior).toBe(original.valorAnterior);
  });

  it("`periodo` no reconocido mantiene el comportamiento actual de serie completa (fallback seguro)", async () => {
    const panel = await getPanel(CLINICA_ID, "24m");
    const metrica = porSlug(panel.metricas, SLUG);
    const original = porSlug(MOCK_METRICAS, SLUG);

    expect(metrica.valorActual).toBe(original.valorActual);
    expect(metrica.valorAnterior).toBe(original.valorAnterior);
  });

  it("3m/6m/12m producen `valorAnterior` distinto entre sí (el delta refleja el horizonte elegido)", async () => {
    const [panel3m, panel6m, panel12m] = await Promise.all([
      getPanel(CLINICA_ID, "3m"),
      getPanel(CLINICA_ID, "6m"),
      getPanel(CLINICA_ID, "12m"),
    ]);

    const valorAnterior3m = porSlug(panel3m.metricas, SLUG).valorAnterior;
    const valorAnterior6m = porSlug(panel6m.metricas, SLUG).valorAnterior;
    const valorAnterior12m = porSlug(panel12m.metricas, SLUG).valorAnterior;

    expect(valorAnterior3m).not.toBe(valorAnterior6m);
    expect(valorAnterior6m).not.toBe(valorAnterior12m);
    expect(valorAnterior3m).not.toBe(valorAnterior12m);
  });

  it("`valorAnterior` de la ventana es el PRIMER punto real de la ventana, no el penúltimo", async () => {
    const panel = await getPanel(CLINICA_ID, "3m");
    const metrica = porSlug(panel.metricas, SLUG);
    const original = porSlug(MOCK_METRICAS, SLUG);
    const puntosReales = original.serie.filter((punto) => !punto.proyectado);
    const ventana3m = puntosReales.slice(-3);

    expect(metrica.valorAnterior).toBe(ventana3m[0].valor);
    expect(metrica.valorAnterior).not.toBe(puntosReales[puntosReales.length - 2].valor);
  });

  it("`valorActual` siempre es el último punto real, sin importar el `periodo`", async () => {
    const original = porSlug(MOCK_METRICAS, SLUG);
    const puntosReales = original.serie.filter((punto) => !punto.proyectado);
    const ultimoReal = puntosReales[puntosReales.length - 1].valor;

    for (const periodo of ["3m", "6m", "12m"] as const) {
      const panel = await getPanel(CLINICA_ID, periodo);
      expect(porSlug(panel.metricas, SLUG).valorActual).toBe(ultimoReal);
    }
  });

  it("el gráfico (serie completa) no se recorta por `periodo` — solo valorActual/valorAnterior cambian", async () => {
    const panelSinPeriodo = await getPanel(CLINICA_ID);
    const panel3m = await getPanel(CLINICA_ID, "3m");

    expect(porSlug(panel3m.metricas, SLUG).serie).toEqual(porSlug(panelSinPeriodo.metricas, SLUG).serie);
  });
});
