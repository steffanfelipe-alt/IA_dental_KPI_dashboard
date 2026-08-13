// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { StepsPanel } from "./StepsPanel";
import type { PasoSistema } from "@/lib/types";

function paso(overrides: Partial<PasoSistema> = {}): PasoSistema {
  return { id: "paso-1", titulo: "Paso de prueba", completado: false, responsable: "clinica", ...overrides };
}

describe("StepsPanel (task 6.1/6.2/6.6)", () => {
  afterEach(cleanup);

  it("starts expanded, with aria-expanded=true and aria-controls wired to a real, visible content region", () => {
    render(<StepsPanel pasos={[]} dependencias={[]} credenciales={[]} />);

    const boton = screen.getByRole("button", { name: "Contraer panel de pasos" });
    expect(boton.getAttribute("aria-expanded")).toBe("true");

    const contenidoId = boton.getAttribute("aria-controls");
    expect(contenidoId).toBeTruthy();
    const contenido = document.getElementById(contenidoId as string);
    expect(contenido).toBeTruthy();
    expect(contenido?.hidden).toBe(false);
  });

  it("toggling the handle flips aria-expanded and hides the content via the native `hidden` attribute, not opacity/width", () => {
    render(<StepsPanel pasos={[]} dependencias={[]} credenciales={[]} />);

    const boton = screen.getByRole("button", { name: "Contraer panel de pasos" });
    fireEvent.click(boton);

    expect(boton.getAttribute("aria-expanded")).toBe("false");
    expect(boton.getAttribute("aria-label")).toBe("Expandir panel de pasos");

    const contenidoId = boton.getAttribute("aria-controls") as string;
    const contenido = document.getElementById(contenidoId) as HTMLElement;
    expect(contenido.hidden).toBe(true);
    // The `hidden` attribute is the mechanism — no opacity/width smuggled in as a parallel hide.
    expect(contenido.style.opacity).toBe("");
    expect(contenido.style.width).toBe("");

    fireEvent.click(boton);
    expect(boton.getAttribute("aria-expanded")).toBe("true");
    expect(contenido.hidden).toBe(false);
  });

  it("allows checking off a clinica-responsable step and does not render an interactive control for an automatico step", () => {
    const pasos = [
      paso({ id: "cliente-1", titulo: "Acción de la clínica", responsable: "clinica", completado: false }),
      paso({ id: "auto-1", titulo: "Paso automático", responsable: "automatico", completado: false }),
    ];
    render(<StepsPanel pasos={pasos} dependencias={[]} credenciales={[]} />);

    const checkboxCliente = screen.getByRole("checkbox", { name: "Acción de la clínica" }) as HTMLInputElement;
    expect(checkboxCliente.checked).toBe(false);
    fireEvent.click(checkboxCliente);
    expect(checkboxCliente.checked).toBe(true);

    expect(screen.getByText("Paso automático")).toBeTruthy();
    expect(screen.queryByRole("checkbox", { name: "Paso automático" })).toBeNull();
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  });

  it("renders steps, dependencies and credentials together in the same retractable region", () => {
    render(
      <StepsPanel
        pasos={[paso()]}
        dependencias={[{ id: "dep-1", titulo: "Dependencia bloqueante", requerida: true, cumplida: false }]}
        credenciales={[{ id: "cred-1", nombre: "Token", estado: "pendiente", instrucciones: "Pegar token." }]}
      />,
    );

    expect(screen.getByText("Pasos")).toBeTruthy();
    expect(screen.getByText("Dependencias")).toBeTruthy();
    expect(screen.getByText("Credenciales")).toBeTruthy();
    expect(screen.getByText("Dependencia bloqueante")).toBeTruthy();
    expect(screen.getByText("Token")).toBeTruthy();
  });
});
