// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { AnclajeProvider, MAX_ANCLADOS, useAnclaje } from "./AnclajeContext";

const STORAGE_KEY = "ia-dental:anclaje:v1";

/** Exercises `useAnclaje` through plain buttons/text, RTL-style, same as `SystemsBlock.test.tsx`. */
function Harness() {
  const { anclados, isAnclado, anclar, desanclar, limiteAlcanzado, seedSiVacio } = useAnclaje();
  return (
    <div>
      <p data-testid="anclados">{anclados.join(",")}</p>
      <p data-testid="limite">{String(limiteAlcanzado)}</p>
      <p data-testid="es-a">{String(isAnclado("sistema-a"))}</p>
      <button onClick={() => anclar("sistema-a")}>anclar-a</button>
      <button onClick={() => anclar("sistema-b")}>anclar-b</button>
      <button onClick={() => anclar("sistema-c")}>anclar-c</button>
      <button onClick={() => anclar("sistema-d")}>anclar-d</button>
      <button onClick={() => anclar("sistema-e")}>anclar-e</button>
      <button onClick={() => desanclar("sistema-a")}>desanclar-a</button>
      <button onClick={() => seedSiVacio(["semilla-1", "semilla-2"])}>seed</button>
    </div>
  );
}

function renderHarness() {
  return render(
    <AnclajeProvider>
      <Harness />
    </AnclajeProvider>,
  );
}

describe("AnclajeContext (task 5.1)", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(cleanup);

  it("useAnclaje throws outside AnclajeProvider — same single-provider-hook contract as useSidebar", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    function SinProveedor() {
      useAnclaje();
      return null;
    }
    expect(() => render(<SinProveedor />)).toThrow("useAnclaje must be used within AnclajeProvider");
    consoleError.mockRestore();
  });

  it("anclar adds a slug, isAnclado reflects it, and it's persisted to localStorage", () => {
    renderHarness();
    fireEvent.click(screen.getByText("anclar-a"));

    expect(screen.getByTestId("anclados").textContent).toBe("sistema-a");
    expect(screen.getByTestId("es-a").textContent).toBe("true");
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "null")).toEqual(["sistema-a"]);
  });

  it("desanclar removes a slug", () => {
    renderHarness();
    fireEvent.click(screen.getByText("anclar-a"));
    fireEvent.click(screen.getByText("desanclar-a"));

    expect(screen.getByTestId("anclados").textContent).toBe("");
    expect(screen.getByTestId("es-a").textContent).toBe("false");
  });

  it(`caps at MAX_ANCLADOS (${MAX_ANCLADOS}) — a 5th anclar is a no-op, limiteAlcanzado flips true at 4`, () => {
    renderHarness();
    fireEvent.click(screen.getByText("anclar-a"));
    fireEvent.click(screen.getByText("anclar-b"));
    fireEvent.click(screen.getByText("anclar-c"));
    fireEvent.click(screen.getByText("anclar-d"));
    expect(screen.getByTestId("limite").textContent).toBe("true");

    fireEvent.click(screen.getByText("anclar-e"));
    expect(screen.getByTestId("anclados").textContent).toBe("sistema-a,sistema-b,sistema-c,sistema-d");
  });

  it("seedSiVacio seeds only the very first time (no localStorage entry yet), never overriding a later state", () => {
    renderHarness();
    fireEvent.click(screen.getByText("seed"));
    expect(screen.getByTestId("anclados").textContent).toBe("semilla-1,semilla-2");

    fireEvent.click(screen.getByText("desanclar-a")); // no-op here (desancla "sistema-a", not present) — just an intervening action
    fireEvent.click(screen.getByText("seed")); // second call: localStorage already has a value, so this is a no-op
    expect(screen.getByTestId("anclados").textContent).toBe("semilla-1,semilla-2");
  });

  it("persists anchoring across a full remount (simulated browser reload)", () => {
    const { unmount } = renderHarness();
    fireEvent.click(screen.getByText("anclar-a"));
    unmount();

    renderHarness();
    expect(screen.getByTestId("anclados").textContent).toBe("sistema-a");
  });
});
