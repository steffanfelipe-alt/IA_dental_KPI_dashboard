// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MetricasEstado } from "./MetricasEstado";
import { getSistema } from "@/lib/data/sistemas";
import { COPY } from "@/lib/copy";
import type { MetricaConObjetivoSistema, Sistema } from "@/lib/types";

/**
 * components/systems/MetricasEstado.test.tsx
 *
 * spec "Métricas y Estado — Direct and Indirect Impact" scenarios (WU-B2,
 * tasks B2.3/B2.4/B2.5): direct metric + delta, indirect metric + the
 * non-promise disclaimer copy, exhaustive indirect listing (no
 * "show more" truncation), and the "not yet measurable" state.
 */
function metrica(overrides: Partial<MetricaConObjetivoSistema> = {}): MetricaConObjetivoSistema {
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
    serie: [],
    impactoScore: 10,
    vulnerabilidadScore: 10,
    sistemasAsociados: [],
    objetivoPostSistema: 70,
    valorAlImplementar: 50,
    relacion: "directa",
    impactoReal: 5,
    ...overrides,
  };
}

function sistema(overrides: Partial<Sistema> = {}): Sistema {
  return {
    slug: "sistema-test",
    nombre: "Sistema de prueba",
    descripcionCorta: "Descripción corta.",
    icono: "bell-ring",
    nivelEmbudo: "retencion",
    categoria: "Comunicación",
    estado: "implementado",
    progresoPct: 100,
    sugeridoPorVeredicto: false,
    anclado: false,
    fechaImplementacion: "2025-11-02",
    pasos: [],
    dependencias: [],
    credenciales: [],
    metricas: [],
    ...overrides,
  };
}

describe("MetricasEstado (tasks B2.3/B2.4/B2.5)", () => {
  afterEach(cleanup);

  it("renders a direct metric under 'Métricas directas' with its signed delta", () => {
    const directa = metrica({ slug: "tasa-no-show", nombre: "Tasa de no-show", relacion: "directa", impactoReal: -4.2, unidad: "%" });
    render(<MetricasEstado sistema={sistema({ metricas: [directa] })} />);

    expect(screen.getByText(COPY.sistemas.metricasYEstado.tituloDirectas)).toBeTruthy();
    expect(screen.getByText("Tasa de no-show")).toBeTruthy();
    expect(screen.getByText("-4,2 %")).toBeTruthy();
  });

  it("renders an indirect metric under 'Métricas indirectas' with the non-promise disclaimer copy", () => {
    const indirecta = metrica({ slug: "tasa-cobro", nombre: "Tasa de cobro", relacion: "indirecta", impactoReal: 3, unidad: "%" });
    render(<MetricasEstado sistema={sistema({ metricas: [indirecta] })} />);

    expect(screen.getByText(COPY.sistemas.metricasYEstado.tituloIndirectas)).toBeTruthy();
    expect(screen.getByText("Tasa de cobro")).toBeTruthy();
    expect(screen.getByText(COPY.sistemas.metricasYEstado.disclaimerIndirectas)).toBeTruthy();
  });

  it("renders all 9 indirect metrics from the recordatorios-turnos mock fixture, no show-more truncation", async () => {
    const recordatorios = await getSistema("clinica-test", "recordatorios-turnos");
    expect(recordatorios).not.toBeNull();

    render(<MetricasEstado sistema={recordatorios as Sistema} />);

    const indirectas = recordatorios!.metricas.filter((m) => m.relacion === "indirecta");
    expect(indirectas).toHaveLength(9);
    for (const indirecta of indirectas) {
      expect(screen.getByText(indirecta.nombre)).toBeTruthy();
    }
    expect(screen.queryByText(/mostrar más/i)).toBeNull();
    expect(screen.queryByText(/ver más/i)).toBeNull();
  });

  it("shows the 'not yet measurable' state instead of a delta when impactoReal is null", () => {
    const sinImplementar = metrica({ slug: "consultas-nuevas", nombre: "Consultas nuevas", relacion: "directa", impactoReal: null });
    render(<MetricasEstado sistema={sistema({ fechaImplementacion: undefined, metricas: [sinImplementar] })} />);

    expect(screen.getByText(COPY.sistemas.metricasYEstado.noImplementadoAun)).toBeTruthy();
  });

  it("renders nothing when the system has no metricas with a relacion set", () => {
    const { container } = render(<MetricasEstado sistema={sistema({ metricas: [] })} />);
    expect(container.firstChild).toBeNull();
  });
});
