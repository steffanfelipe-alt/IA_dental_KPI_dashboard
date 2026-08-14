// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { Sparkline } from "./Sparkline";

/**
 * `ResponsiveContainer` measures 0x0 in jsdom (design doc gotcha) — mock
 * `recharts` and assert the wrapping `div`'s color class/stroke prop
 * instead of chart SVG output.
 */
let lastStroke: string | undefined;

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Line: ({ stroke }: { stroke: string }) => {
    lastStroke = stroke;
    return null;
  },
}));

const serie = { "2026-01": 22.0, "2026-02": 18.9 };

/**
 * U2 (task 3.5): "dirección null renderiza neutro" — pins the exact
 * neutral behavior at the component boundary, one layer below the full
 * `/onboarding/[id]/veredicto` page (which is gated behind
 * auth+onboarding-completion and isn't reachable by a bare `npm run dev`
 * visual check without seeding session/clinic state).
 */
describe("Sparkline color by direccion (task 3.4/3.5)", () => {
  afterEach(cleanup);

  it("estado null → neutral blue stroke, no state-* class", () => {
    const { container } = render(<Sparkline serie={serie} estado={null} />);

    expect(lastStroke).toBe("#2563eb");
    expect(container.firstElementChild?.className).not.toMatch(/text-state-/);
  });

  it("estado good → text-state-good class + currentColor stroke", () => {
    const { container } = render(<Sparkline serie={serie} estado="good" />);

    expect(lastStroke).toBe("currentColor");
    expect(container.firstElementChild?.className).toMatch(/text-state-good/);
  });

  it("estado bad → text-state-bad class + currentColor stroke", () => {
    const { container } = render(<Sparkline serie={serie} estado="bad" />);

    expect(lastStroke).toBe("currentColor");
    expect(container.firstElementChild?.className).toMatch(/text-state-bad/);
  });

  it("estado flat → text-state-flat class + currentColor stroke", () => {
    const { container } = render(<Sparkline serie={serie} estado="flat" />);

    expect(lastStroke).toBe("currentColor");
    expect(container.firstElementChild?.className).toMatch(/text-state-flat/);
  });
});
