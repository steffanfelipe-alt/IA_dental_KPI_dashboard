// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { CredentialItem } from "./CredentialItem";
import type { CredencialSistema } from "@/lib/types";

function credencial(overrides: Partial<CredencialSistema> = {}): CredencialSistema {
  return { id: "cred-1", nombre: "Token de API", estado: "pendiente", instrucciones: "Pegar el token generado.", ...overrides };
}

const VALOR_SECRETO = "sk-super-secreto-123";

describe("CredentialItem (task 6.3/6.6)", () => {
  afterEach(cleanup);

  it("never shows a raw credential value field: only estado + instrucciones render for a non-pending credential", () => {
    render(<CredentialItem credencial={credencial({ estado: "verificada" })} />);

    expect(screen.getByText("Verificada")).toBeTruthy();
    expect(screen.getByText("Pegar el token generado.")).toBeTruthy();
    expect(screen.queryByLabelText(/valor de token de api/i)).toBeNull();
  });

  it("renders the pending-value input as write-only (type=password) and never echoes the typed value anywhere else in the DOM", () => {
    const { container } = render(<CredentialItem credencial={credencial({ estado: "pendiente" })} />);

    const input = screen.getByLabelText(/valor de token de api/i) as HTMLInputElement;
    expect(input.getAttribute("type")).toBe("password");

    fireEvent.change(input, { target: { value: VALOR_SECRETO } });
    expect(input.value).toBe(VALOR_SECRETO); // controlled input needs this while typing — the input's own live value

    // No OTHER node in the tree ever echoes the typed value (no preview/confirmation leak).
    expect(container.textContent).not.toContain(VALOR_SECRETO);
  });

  it("clears the input immediately on submit and the value never appears anywhere in rendered output afterward", () => {
    const { container } = render(<CredentialItem credencial={credencial({ estado: "pendiente" })} />);

    const input = screen.getByLabelText(/valor de token de api/i) as HTMLInputElement;
    const boton = screen.getByRole("button", { name: "Enviar" });

    fireEvent.change(input, { target: { value: VALOR_SECRETO } });
    fireEvent.click(boton);

    expect(input.value).toBe("");
    expect(container.innerHTML).not.toContain(VALOR_SECRETO);
    expect(container.textContent).not.toContain(VALOR_SECRETO);
    expect(screen.getByText("Enviado. Lo vamos a verificar.")).toBeTruthy();
  });

  it("exposes no `valor` field on the CredencialSistema type at all — nothing to leak by construction", () => {
    // lib/types.ts::CredencialSistema deliberately has no `valor` field.
    // This documents that invariant at the component boundary: even a
    // credential explicitly given every other field renders no value-like
    // string, regardless of estado.
    const cred = credencial({ estado: "recibida", instrucciones: "Ya la recibimos, la estamos verificando." });
    const { container } = render(<CredentialItem credencial={cred} />);
    expect(container.innerHTML).not.toMatch(/sk-|secret|password-value/i);
  });
});
