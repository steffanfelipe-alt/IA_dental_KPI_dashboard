// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { AnchorButton } from "./AnchorButton";
import { AnclajeProvider } from "@/lib/anclaje/AnclajeContext";
import { COPY } from "@/lib/copy";
import type { EstadoSistema } from "@/lib/types";

function renderBoton(sistema: { slug: string; nombre: string; estado: EstadoSistema }) {
  return render(
    <AnclajeProvider>
      <AnchorButton sistema={sistema} />
    </AnclajeProvider>,
  );
}

describe("AnchorButton (task 5.4)", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(cleanup);

  it("renders nothing for a non-disponible system — anchoring only applies to disponible", () => {
    const { container } = renderBoton({ slug: "s1", nombre: "Sistema uno", estado: "en_proceso" });
    expect(container.textContent).toBe("");
  });

  it("shows Anclar for a disponible, non-anchored system; clicking switches it to Desanclar", () => {
    renderBoton({ slug: "s1", nombre: "Sistema uno", estado: "disponible" });

    fireEvent.click(screen.getByRole("button", { name: `${COPY.panel.accionAnclar} Sistema uno` }));

    expect(screen.getByRole("button", { name: `${COPY.panel.accionDesanclar} Sistema uno` })).toBeTruthy();
  });

  it("clicking Desanclar switches it back to Anclar", () => {
    renderBoton({ slug: "s1", nombre: "Sistema uno", estado: "disponible" });

    fireEvent.click(screen.getByRole("button", { name: `${COPY.panel.accionAnclar} Sistema uno` }));
    fireEvent.click(screen.getByRole("button", { name: `${COPY.panel.accionDesanclar} Sistema uno` }));

    expect(screen.getByRole("button", { name: `${COPY.panel.accionAnclar} Sistema uno` })).toBeTruthy();
  });

  it("disables Anclar and shows the exact limit copy once 4 systems are anchored via AnchorButton", () => {
    const sistemas = Array.from({ length: 5 }, (_, i) => ({ slug: `s${i}`, nombre: `Sistema ${i}`, estado: "disponible" as const }));
    render(
      <AnclajeProvider>
        {sistemas.map((sistema) => (
          <AnchorButton key={sistema.slug} sistema={sistema} />
        ))}
      </AnclajeProvider>,
    );

    for (let i = 0; i < 4; i++) {
      fireEvent.click(screen.getByRole("button", { name: `${COPY.panel.accionAnclar} Sistema ${i}` }));
    }

    const quinto = screen.getByRole("button", { name: `${COPY.panel.accionAnclar} Sistema 4` }) as HTMLButtonElement;
    expect(quinto.disabled).toBe(true);
    expect(screen.getByText(COPY.panel.limiteAnclados)).toBeTruthy();
  });
});
