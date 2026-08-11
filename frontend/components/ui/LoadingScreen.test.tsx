// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { LoadingScreen } from "./LoadingScreen";

describe("LoadingScreen", () => {
  afterEach(cleanup);

  it("shows the default tagline when no mensaje is passed", () => {
    render(<LoadingScreen />);

    expect(screen.getByText("AI")).toBeTruthy();
    expect(screen.getByText(/dental dashboard/)).toBeTruthy();
  });

  it("shows the custom mensaje in place of the default tagline when passed", () => {
    render(<LoadingScreen mensaje="Esto puede tardar un momento…" />);

    expect(screen.getByText("Esto puede tardar un momento…")).toBeTruthy();
    expect(screen.queryByText(/dental dashboard/)).toBeNull();
  });
});
