// @vitest-environment jsdom
import { describe, expect, it, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { InformeText } from "./InformeText";

/**
 * Task 4.5: feed prose into `InformeText`, assert heading/paragraph split.
 * Follows this repo's manual `afterEach(cleanup)` convention (no global
 * RTL auto-cleanup exists).
 */
describe("InformeText (task 4.5)", () => {
  afterEach(cleanup);

  it("splits blank-line-separated blocks into H2/H3 headings and paragraphs", () => {
    const texto = `# Resumen ejecutivo

Primer párrafo de prueba.

## Fortalezas

Segundo párrafo de prueba.`;

    render(<InformeText texto={texto} />);

    const h2 = screen.getByRole("heading", { name: "Resumen ejecutivo" });
    const h3 = screen.getByRole("heading", { name: "Fortalezas" });
    expect(h2.tagName).toBe("H2");
    expect(h3.tagName).toBe("H3");
    expect(screen.getByText("Primer párrafo de prueba.")).toBeTruthy();
    expect(screen.getByText("Segundo párrafo de prueba.")).toBeTruthy();
  });

  it("does not treat a multi-line block as a heading, even if it starts with #", () => {
    render(<InformeText texto={"# Título\nSegunda línea sin blank de por medio"} />);

    expect(screen.queryByRole("heading")).toBeNull();
    expect(screen.getByText(/Título/)).toBeTruthy();
  });

  it("ignores blank blocks produced by extra blank lines between sections", () => {
    const texto = "# Único título\n\n\n\nÚnico párrafo.";

    render(<InformeText texto={texto} />);

    expect(screen.getByRole("heading", { name: "Único título" })).toBeTruthy();
    expect(screen.getByText("Único párrafo.")).toBeTruthy();
  });
});
