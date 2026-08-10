"use client";

import { useEffect, useRef, useState } from "react";

/**
 * lib/hooks/useIdempotencyKey.ts
 *
 * D3: generates a client-side `Idempotency-Key` for `POST /clinicas`
 * inside a `useEffect` on mount, NEVER in the render body. Generating it
 * during render would produce different values on the server-rendered
 * pass vs. the client hydration pass — a server/client mismatch that
 * trips a React hydration error. `useRef` holds the value so it's stable
 * across re-renders/retries of the same submit; `useState` mirrors it so
 * consumers re-render once the key becomes available (it's `undefined`
 * until the first effect flush completes).
 */
export function useIdempotencyKey(): string | undefined {
  const keyRef = useRef<string | undefined>(undefined);
  const [key, setKey] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!keyRef.current) {
      keyRef.current = crypto.randomUUID();
      setKey(keyRef.current);
    }
  }, []);

  return key;
}
