"use client";

import { useState } from "react";
import type { EstadoSistema, Sistema } from "@/lib/types";
import { COPY } from "@/lib/copy";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { EmptyState } from "@/components/ui/EmptyState";
import { SystemBadge } from "./SystemBadge";
import { SystemStatusChip } from "./SystemStatusChip";

/** SPEC "Pantalla A": A3 shows only these three, in this order — never `disponible`. */
const ORDEN_A3: EstadoSistema[] = ["en_proceso", "sugerido", "implementado"];

/** SPEC "Manual System Anchoring (A3-bis)": hard cap, exact copy below. */
const MAX_ANCLADOS = 4;

function PinIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-4 w-4" aria-hidden="true">
      <path d="M12 3v7M9 10h6l3 4H6l3-4z" />
      <path d="M12 14v7" />
    </svg>
  );
}

/**
 * components/systems/SystemsBlock.tsx
 *
 * A3 + A3-bis (SPEC "Pantalla A — Panel prioritario", "Manual System
 * Anchoring"). Client component: anchoring is in-memory, optimistic
 * state per the design's data flow ("client leaves ... in-memory
 * optimistic state, onToggle callbacks — Slice2 wires PUT"), no
 * localStorage, no backend call yet.
 *
 * Takes the FULL `sistemas` list (not pre-filtered) and does its own
 * partitioning — this fixes a small inconsistency inherited from PR1:
 * `lib/data/panel.ts`'s own header comment already said "the
 * display-only ordering/exclusion rules... belong to the Pantalla A
 * component, not [the loader]", but the loader was still filtering out
 * non-anchored `disponible` systems itself. That filter is removed in
 * this PR (see `lib/data/panel.ts`) so this component is the single
 * place that decides what's visible:
 *   - A3 main list: `en_proceso`/`sugerido`/`implementado`, `ORDEN_A3`
 *     order, `disponible` NEVER appears here.
 *   - A3-bis "Anclados por la clínica": `disponible` systems currently
 *     anchored (local state, seeded from `Sistema.anclado`), each with a
 *     "Desanclar" action, max 4, "impacted metrics" instead of a
 *     suggestion motive, no dashed arc (SPEC: "no motive line").
 *   - a compact "Otros sistemas que podés anclar" list of `disponible`
 *     systems NOT yet anchored — this is the "anchor a system" action
 *     itself; SPEC doesn't pin its exact location, and Pantalla A's own
 *     wireframe only shows the already-anchored group, so this is a
 *     deliberately minimal (name + button, not a full system card)
 *     affordance kept local to this component rather than duplicating
 *     Pantalla B's full catalog (PR5) a PR early.
 *
 * Because both groups are derived from `sistema.estado` on every render
 * (not from a separately-tracked "was anchored" flag), a system that
 * transitions to `sugerido`/`en_proceso` automatically leaves the
 * anchored group and renders exactly once, in A3 — no extra bookkeeping
 * needed for that SPEC scenario.
 */
export function SystemsBlock({ sistemas }: { sistemas: Sistema[] }) {
  const [anclados, setAnclados] = useState<Set<string>>(
    () => new Set(sistemas.filter((sistema) => sistema.estado === "disponible" && sistema.anclado).map((sistema) => sistema.slug)),
  );

  const grupoPrincipal = ORDEN_A3.flatMap((estado) => sistemas.filter((sistema) => sistema.estado === estado));
  const grupoAnclado = sistemas.filter((sistema) => sistema.estado === "disponible" && anclados.has(sistema.slug));
  const candidatos = sistemas.filter((sistema) => sistema.estado === "disponible" && !anclados.has(sistema.slug));
  const limiteAlcanzado = grupoAnclado.length >= MAX_ANCLADOS;

  function anclar(slug: string) {
    setAnclados((prev) => {
      if (prev.size >= MAX_ANCLADOS) return prev;
      const next = new Set(prev);
      next.add(slug);
      return next;
    });
  }

  function desanclar(slug: string) {
    setAnclados((prev) => {
      const next = new Set(prev);
      next.delete(slug);
      return next;
    });
  }

  return (
    <section className="flex flex-col gap-6">
      <div>
        <SectionHeading title={COPY.panel.bloqueSistemas} subtitle="en proceso → sugeridos → implementados" />
        {grupoPrincipal.length === 0 ? (
          <EmptyState title="Todavía no hay sistemas en curso, sugeridos o implementados." />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {grupoPrincipal.map((sistema) => (
              <li key={sistema.slug} className="flex items-start gap-3 rounded-2xl border border-border-subtle bg-surface p-4">
                <SystemBadge estado={sistema.estado} progresoPct={sistema.progresoPct} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text-strong">{sistema.nombre}</p>
                  <div className="mt-1">
                    <SystemStatusChip estado={sistema.estado} />
                  </div>
                  {sistema.estado === "sugerido" && sistema.motivoSugerencia ? (
                    <p className="mt-2 line-clamp-2 text-xs text-text-muted">{sistema.motivoSugerencia}</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <p className="text-xs font-semibold tracking-wide text-text-muted uppercase">
          {COPY.panel.bloqueSistemasAnclados} · {grupoAnclado.length} de {MAX_ANCLADOS}
        </p>

        {grupoAnclado.length === 0 ? (
          <p className="mt-2 text-sm text-text-muted">Todavía no anclaste ningún sistema.</p>
        ) : (
          <ul className="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {grupoAnclado.map((sistema) => (
              <li key={sistema.slug} className="flex items-start gap-3 rounded-2xl border border-border-subtle bg-surface p-4">
                <span className="mt-0.5 text-sys-idle">
                  <PinIcon />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text-strong">{sistema.nombre}</p>
                  <p className="mt-1 truncate text-xs text-text-muted">
                    Impacta: {sistema.metricas.map((metrica) => metrica.nombre).join(", ") || "—"}
                  </p>
                  <button
                    type="button"
                    onClick={() => desanclar(sistema.slug)}
                    aria-label={`${COPY.panel.accionDesanclar} ${sistema.nombre}`}
                    className="mt-2 text-xs font-medium text-primary-600 hover:underline"
                  >
                    {COPY.panel.accionDesanclar}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {candidatos.length > 0 ? (
          <div className="mt-3">
            <p className="text-xs text-text-muted">{COPY.panel.bloqueSistemasCandidatos}</p>
            <ul className="mt-1 flex flex-wrap gap-2">
              {candidatos.map((sistema) => (
                <li key={sistema.slug}>
                  <button
                    type="button"
                    onClick={() => anclar(sistema.slug)}
                    disabled={limiteAlcanzado}
                    aria-label={`${COPY.panel.accionAnclar} ${sistema.nombre}`}
                    className="rounded-full border border-border-subtle px-3 py-1 text-xs font-medium text-text-body hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    + {sistema.nombre}
                  </button>
                </li>
              ))}
            </ul>
            {limiteAlcanzado ? <p className="mt-1 text-xs text-state-bad">{COPY.panel.limiteAnclados}</p> : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
