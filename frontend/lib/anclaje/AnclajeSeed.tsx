"use client";

import { useEffect } from "react";
import { useAnclaje } from "./AnclajeContext";

/**
 * lib/anclaje/AnclajeSeed.tsx
 *
 * One-shot, idempotent bridge between a server-fetched `Sistema[]` and
 * the client-only `AnclajeContext`: seeds the initially-anchored
 * `disponible` systems (mock's `anclado: true`) the very first time this
 * browser has no `localStorage` entry yet (`seedSiVacio` no-ops after
 * that — see its doc in `AnclajeContext.tsx`). Rendered from BOTH
 * `/panel` (`SystemsBlock`) and `/sistemas` (catalog page), since either
 * can be the first screen a clinic visits; whichever mounts first wins
 * the seed, the other call is a harmless no-op.
 */
export function AnclajeSeed({ slugs }: { slugs: string[] }) {
  const { seedSiVacio } = useAnclaje();

  useEffect(() => {
    seedSiVacio(slugs);
    // Seed once, with the slugs known at mount time — re-running on every
    // `slugs` change would fight the clinic's own anclar/desanclar edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
