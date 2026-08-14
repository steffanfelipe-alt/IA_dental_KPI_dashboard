"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

/**
 * lib/anclaje/AnclajeContext.tsx
 *
 * SPEC "Manual System Anchoring (A3-bis)": anchoring MUST be "shared
 * between `/panel` and the `/sistemas` catalog via a client-side store
 * (Context + `localStorage`), persisting across reload within the same
 * browser." `zustand` is NOT a dependency of this project (checked
 * `package.json`) — a plain React Context replaces the design's
 * alternative without adding one, same shape `AppShell`'s sidebar-collapse
 * context already uses (`useX` hook that throws outside its provider).
 *
 * Slice-1 client-only state: this is per-browser `localStorage`, NOT
 * per-clinic backend persistence — Slice-2 replaces the read/write helpers
 * below with a real `GET`/`PUT` against the clinic's anchored-systems
 * endpoint; every consumer only sees `anclar`/`desanclar`/`isAnclado`, so
 * that swap stays isolated to this file.
 */

export const MAX_ANCLADOS = 4;

const STORAGE_KEY = "ia-dental:anclaje:v1";

interface AnclajeContextValue {
  anclados: string[];
  isAnclado: (slug: string) => boolean;
  anclar: (slug: string) => void;
  desanclar: (slug: string) => void;
  limiteAlcanzado: boolean;
  /**
   * Seeds the store from `slugs` ONLY the very first time this browser
   * ever runs the app (no `localStorage` entry yet). Once anything has
   * been written — a real anclar/desanclar, or a previous seed call, even
   * an empty one — this is a no-op, so it never overrides what the
   * clinic actually left anchored.
   */
  seedSiVacio: (slugs: string[]) => void;
}

const AnclajeContext = createContext<AnclajeContextValue | null>(null);

function leerStorage(): string[] | null {
  if (typeof window === "undefined") return null;
  try {
    const crudo = window.localStorage.getItem(STORAGE_KEY);
    if (crudo === null) return null;
    const parseado: unknown = JSON.parse(crudo);
    return Array.isArray(parseado) ? parseado.filter((valor): valor is string => typeof valor === "string") : null;
  } catch {
    return null;
  }
}

function escribirStorage(slugs: string[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(slugs));
  } catch {
    // Private mode / quota exceeded: degrade to in-memory-only for this session instead of crashing anchoring.
  }
}

/** Throws outside `AnclajeProvider` — same "single-provider hook" convention `AppShell`'s `useSidebar` already uses in this codebase. */
export function useAnclaje(): AnclajeContextValue {
  const context = useContext(AnclajeContext);
  if (!context) {
    throw new Error("useAnclaje must be used within AnclajeProvider");
  }
  return context;
}

export function AnclajeProvider({ children }: { children: ReactNode }) {
  const [anclados, setAnclados] = useState<string[]>([]);
  const hidratadoRef = useRef(false);

  // Hydrate from a previous session's localStorage. Deliberately in a
  // mount-only effect, not the render body — reading `window` during
  // render would mismatch the server-rendered pass (see
  // `lib/hooks/useIdempotencyKey.ts` for the same ref-guarded discipline).
  useEffect(() => {
    if (!hidratadoRef.current) {
      hidratadoRef.current = true;
      setAnclados((prev) => {
        const almacenado = leerStorage();
        return almacenado !== null ? almacenado.slice(0, MAX_ANCLADOS) : prev;
      });
    }
  }, []);

  const anclar = useCallback((slug: string) => {
    setAnclados((prev) => {
      if (prev.includes(slug) || prev.length >= MAX_ANCLADOS) return prev;
      const next = [...prev, slug];
      escribirStorage(next);
      return next;
    });
  }, []);

  const desanclar = useCallback((slug: string) => {
    setAnclados((prev) => {
      const next = prev.filter((anclado) => anclado !== slug);
      escribirStorage(next);
      return next;
    });
  }, []);

  const isAnclado = useCallback((slug: string) => anclados.includes(slug), [anclados]);

  const seedSiVacio = useCallback((slugs: string[]) => {
    if (leerStorage() !== null) return;
    const next = slugs.slice(0, MAX_ANCLADOS);
    escribirStorage(next);
    setAnclados(next);
  }, []);

  const value = useMemo<AnclajeContextValue>(
    () => ({ anclados, isAnclado, anclar, desanclar, limiteAlcanzado: anclados.length >= MAX_ANCLADOS, seedSiVacio }),
    [anclados, isAnclado, anclar, desanclar, seedSiVacio],
  );

  return <AnclajeContext.Provider value={value}>{children}</AnclajeContext.Provider>;
}
