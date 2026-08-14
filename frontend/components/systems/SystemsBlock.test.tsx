// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SystemsBlock } from "./SystemsBlock";
import { AnclajeProvider } from "@/lib/anclaje/AnclajeContext";
import { COPY } from "@/lib/copy";
import type { Sistema } from "@/lib/types";

/** `SystemsBlock` reads anchoring from the shared `AnclajeContext` (task 5.3) — every render needs the provider. */
function renderSystemsBlock(sistemas: Sistema[]) {
  return render(
    <AnclajeProvider>
      <SystemsBlock sistemas={sistemas} />
    </AnclajeProvider>,
  );
}

function sistema(overrides: Partial<Sistema> = {}): Sistema {
  return {
    slug: "sistema-test",
    nombre: "Sistema de prueba",
    descripcionCorta: "Descripción corta.",
    icono: "bell-ring",
    nivelEmbudo: "retencion",
    categoria: "Comunicación",
    estado: "disponible",
    progresoPct: 0,
    sugeridoPorVeredicto: false,
    anclado: false,
    pasos: [],
    dependencias: [],
    credenciales: [],
    metricas: [],
    ...overrides,
  };
}

describe("SystemsBlock (task 4.3/4.4)", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(cleanup);

  it("disables the anchor action with the exact limit copy once 4 systems are anchored", () => {
    const anclados = Array.from({ length: 4 }, (_, i) =>
      sistema({ slug: `anclado-${i}`, nombre: `Anclado ${i}`, estado: "disponible", anclado: true }),
    );
    const candidato = sistema({ slug: "candidato-1", nombre: "Candidato uno", estado: "disponible", anclado: false });

    renderSystemsBlock([...anclados, candidato]);

    const boton = screen.getByRole("button", { name: `${COPY.panel.accionAnclar} Candidato uno` }) as HTMLButtonElement;
    expect(boton.disabled).toBe(true);
    expect(screen.getByText(COPY.panel.limiteAnclados)).toBeTruthy();
    expect(screen.getByText(`${COPY.panel.bloqueSistemasAnclados} · 4 de 4`)).toBeTruthy();
  });

  it("still allows anchoring (button enabled, no limit copy) when under 4 anchored", () => {
    const anclados = Array.from({ length: 2 }, (_, i) =>
      sistema({ slug: `anclado-${i}`, nombre: `Anclado ${i}`, estado: "disponible", anclado: true }),
    );
    const candidato = sistema({ slug: "candidato-1", nombre: "Candidato uno", estado: "disponible", anclado: false });

    renderSystemsBlock([...anclados, candidato]);

    const boton = screen.getByRole("button", { name: `${COPY.panel.accionAnclar} Candidato uno` }) as HTMLButtonElement;
    expect(boton.disabled).toBe(false);
    expect(screen.queryByText(COPY.panel.limiteAnclados)).toBeNull();
  });

  it("removes a system from the anchored group once it transitions to sugerido, rendering it only once", () => {
    const promovido = sistema({
      slug: "promovido",
      nombre: "Sistema promovido",
      estado: "sugerido",
      anclado: true,
      motivoSugerencia: "Motivo de la sugerencia.",
    });

    renderSystemsBlock([promovido]);

    expect(screen.getAllByText("Sistema promovido")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: `${COPY.panel.accionDesanclar} Sistema promovido` })).toBeNull();
    expect(screen.getByText(`${COPY.panel.bloqueSistemasAnclados} · 0 de 4`)).toBeTruthy();
  });

  it("removes a system from the anchored group once it transitions to en_proceso, rendering it only once", () => {
    const promovido = sistema({
      slug: "promovido-2",
      nombre: "Sistema en curso",
      estado: "en_proceso",
      anclado: true,
    });

    renderSystemsBlock([promovido]);

    expect(screen.getAllByText("Sistema en curso")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: `${COPY.panel.accionDesanclar} Sistema en curso` })).toBeNull();
  });

  it("never shows a non-anchored disponible system in the main A3 list", () => {
    const disponible = sistema({ slug: "disponible-1", nombre: "Sistema disponible", estado: "disponible", anclado: false });

    renderSystemsBlock([disponible]);

    // Only rendered once, as a compact anchor-candidate button, not as a full A3 card with a status chip.
    expect(screen.getAllByRole("button", { name: `${COPY.panel.accionAnclar} Sistema disponible` })).toHaveLength(1);
    expect(screen.queryByText("Disponible")).toBeNull();
  });
});
