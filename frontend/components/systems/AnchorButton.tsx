"use client";

import { useAnclaje } from "@/lib/anclaje/AnclajeContext";
import { COPY } from "@/lib/copy";
import type { EstadoSistema } from "@/lib/types";

/**
 * components/systems/AnchorButton.tsx
 *
 * SPEC "Manual System Anchoring (A3-bis)": anchoring only applies to
 * `disponible` systems — the same gate `SystemsBlock` already applies to
 * its own anchored group. Renders nothing for any other `estado`, so
 * callers (catalog, detail page) can render it unconditionally per
 * system without duplicating that business rule.
 *
 * Reads/writes the shared `AnclajeContext` (task 5.1) — this is what
 * makes anchoring from `/sistemas` show up on `/panel` and survive
 * reload (SPEC scenarios "Anchoring shared across pages", "Anchoring
 * survives reload"). Exact limit copy, same as `SystemsBlock`'s
 * candidate list — `COPY.panel.limiteAnclados`, do not reword.
 */
export function AnchorButton({ sistema }: { sistema: { slug: string; nombre: string; estado: EstadoSistema } }) {
  const { isAnclado, anclar, desanclar, limiteAlcanzado } = useAnclaje();

  if (sistema.estado !== "disponible") return null;

  if (isAnclado(sistema.slug)) {
    return (
      <button
        type="button"
        onClick={() => desanclar(sistema.slug)}
        aria-label={`${COPY.panel.accionDesanclar} ${sistema.nombre}`}
        className="rounded-full border border-border-subtle px-3 py-1 text-xs font-medium text-primary-600 hover:bg-canvas"
      >
        {COPY.panel.accionDesanclar}
      </button>
    );
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        type="button"
        onClick={() => anclar(sistema.slug)}
        disabled={limiteAlcanzado}
        aria-label={`${COPY.panel.accionAnclar} ${sistema.nombre}`}
        className="rounded-full border border-border-subtle px-3 py-1 text-xs font-medium text-text-body hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-50"
      >
        {COPY.panel.accionAnclar}
      </button>
      {limiteAlcanzado ? <p className="text-center text-xs text-state-bad">{COPY.panel.limiteAnclados}</p> : null}
    </div>
  );
}
