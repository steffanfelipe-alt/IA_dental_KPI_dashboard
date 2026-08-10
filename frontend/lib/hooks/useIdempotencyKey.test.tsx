// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { useIdempotencyKey } from "./useIdempotencyKey";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function TestComponent({ onRender }: { onRender: (key: string | undefined) => void }) {
  const key = useIdempotencyKey();
  // Captured synchronously during the render body — BEFORE any effect has
  // had a chance to run.
  onRender(key);
  return <div data-testid="key">{key ?? "none"}</div>;
}

describe("useIdempotencyKey", () => {
  it("is undefined during the first render body and only set after mount (D3 hydration safety)", () => {
    const randomUUIDSpy = vi.spyOn(crypto, "randomUUID");
    const renderedKeys: Array<string | undefined> = [];

    const { getByTestId } = render(<TestComponent onRender={(key) => renderedKeys.push(key)} />);

    // First render (pre-effect): no key yet, crypto.randomUUID not called.
    // We can't assert on randomUUIDSpy's call count at the exact moment of
    // that first render (it already ran by the time this line executes,
    // since render() flushes effects synchronously), so the ordering
    // guarantee instead comes from the captured value itself: if the hook
    // generated the key in the render body, `renderedKeys[0]` would
    // already be a UUID, not `undefined`.
    expect(renderedKeys[0]).toBeUndefined();

    // After the mount effect flushes (React Testing Library's render()
    // wraps in act(), which flushes effects synchronously), a second
    // render happens with a stable, valid UUID.
    const finalKey = getByTestId("key").textContent;
    expect(finalKey).toMatch(UUID_PATTERN);
    expect(randomUUIDSpy).toHaveBeenCalledTimes(1);
  });

  it("keeps the same key across re-renders (stable via useRef)", () => {
    const renderedKeys: Array<string | undefined> = [];
    function Consumer() {
      renderedKeys.push(useIdempotencyKey());
      return null;
    }

    const { rerender } = render(<Consumer />);
    // First render is pre-effect (undefined); the effect's setKey then
    // triggers a second render with the generated UUID.
    const keyAfterMount = renderedKeys.at(-1);
    expect(keyAfterMount).toMatch(UUID_PATTERN);

    rerender(<Consumer />);

    expect(renderedKeys.at(-1)).toBe(keyAfterMount);
  });
});
