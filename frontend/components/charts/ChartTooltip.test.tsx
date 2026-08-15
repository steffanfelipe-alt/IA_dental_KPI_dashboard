// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { ChartTooltip } from "./ChartTooltip";

/**
 * spec "Distribution Chart Hover" scenarios: count + derived share
 * (`cantidad / Σcantidad`), and a safe 0% (no NaN/Infinity/throw) when
 * the dataset total is 0.
 */
describe("ChartTooltip (task A.3/A.4)", () => {
  afterEach(cleanup);

  const payload = [
    {
      payload: { estado: "PROBLEM", label: "Problema", cantidad: 12 },
    },
  ] as never;

  it("row cantidad=12 of total=30 renders count + 40% share", () => {
    const { getByText } = render(<ChartTooltip active payload={payload} total={30} />);

    expect(getByText("12 (40%)")).toBeTruthy();
  });

  it("zero-total dataset renders a safe 0% share, no NaN/Infinity", () => {
    const zeroPayload = [
      {
        payload: { estado: "PROBLEM", label: "Problema", cantidad: 0 },
      },
    ] as never;

    const { getByText, queryByText } = render(<ChartTooltip active payload={zeroPayload} total={0} />);

    expect(getByText("0 (0%)")).toBeTruthy();
    expect(queryByText(/NaN/)).toBeNull();
    expect(queryByText(/Infinity/)).toBeNull();
  });

  it("inactive (not hovered) renders nothing", () => {
    const { container } = render(<ChartTooltip active={false} payload={payload} total={30} />);

    expect(container.firstChild).toBeNull();
  });

  it("no payload renders nothing", () => {
    const { container } = render(<ChartTooltip active payload={[]} total={30} />);

    expect(container.firstChild).toBeNull();
  });
});
