// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SystemMedallion } from "./SystemMedallion";
import type { EstadoSistema } from "@/lib/types";

function sistema(overrides: Partial<{ slug: string; nombre: string; icono: string; estado: EstadoSistema }> = {}) {
  return { slug: "sistema-test", nombre: "Sistema de prueba", icono: "bell-ring", estado: "implementado" as EstadoSistema, ...overrides };
}

describe("SystemMedallion (task 7.1/7.4)", () => {
  afterEach(cleanup);

  it("is a single link to the system detail page with ?from=catalogo", () => {
    render(<SystemMedallion sistema={sistema({ slug: "recordatorios-turnos", nombre: "Recordatorios" })} />);

    const link = screen.getByRole("link", { name: "Recordatorios" }) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("/sistemas/recordatorios-turnos?from=catalogo");
  });

  it("enforces a minimum 44x44px hit target on the click target itself", () => {
    render(<SystemMedallion sistema={sistema()} />);

    const link = screen.getByRole("link") as HTMLAnchorElement;
    expect(link.style.minWidth).toBe("44px");
    expect(link.style.minHeight).toBe("44px");
  });

  it("resolves a known icono name to its Lucide icon (renders an svg, not text, inside the ring)", () => {
    render(<SystemMedallion sistema={sistema({ icono: "bell-ring" })} />);

    const link = screen.getByRole("link");
    expect(link.querySelector("svg")).toBeTruthy();
  });

  it("falls back to a generic icon for an unrecognized icono value instead of crashing or rendering nothing", () => {
    render(<SystemMedallion sistema={sistema({ icono: "not-a-real-lucide-icon" })} />);

    const link = screen.getByRole("link");
    expect(link.querySelector("svg")).toBeTruthy();
  });

  it("uses a dashed ring for sugerido and a solid ring for implementado (ring encodes state)", () => {
    const { rerender } = render(<SystemMedallion sistema={sistema({ estado: "sugerido" })} />);
    let ring = screen.getByRole("link").querySelector("span[aria-hidden='true']") as HTMLElement;
    expect(ring.className).toContain("border-dashed");
    expect(ring.className).toContain("border-sys-suggested");

    rerender(<SystemMedallion sistema={sistema({ estado: "implementado" })} />);
    ring = screen.getByRole("link").querySelector("span[aria-hidden='true']") as HTMLElement;
    expect(ring.className).not.toContain("border-dashed");
    expect(ring.className).toContain("border-sys-live");
  });

  it("renders the system name outside the icon ring, not inside it", () => {
    render(<SystemMedallion sistema={sistema({ nombre: "Nombre visible" })} />);

    const ring = screen.getByRole("link").querySelector("span[aria-hidden='true']") as HTMLElement;
    expect(ring.textContent).toBe("");
    expect(screen.getByText("Nombre visible")).toBeTruthy();
  });

  it("shows a disponible-state ring (Pantalla B is exhaustive, unlike A3 which never shows disponible)", () => {
    render(<SystemMedallion sistema={sistema({ estado: "disponible" })} />);

    const ring = screen.getByRole("link").querySelector("span[aria-hidden='true']") as HTMLElement;
    expect(ring.className).toContain("border-sys-idle");
  });
});
