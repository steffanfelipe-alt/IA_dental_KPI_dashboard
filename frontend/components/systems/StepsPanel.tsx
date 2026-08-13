"use client";

import { useId, useState } from "react";
import type { CredencialSistema, DependenciaSistema, PasoSistema } from "@/lib/types";
import { StepChecklist } from "./StepChecklist";
import { DependenciesList } from "./DependenciesList";
import { CredentialItem } from "./CredentialItem";

/**
 * components/systems/StepsPanel.tsx
 *
 * Pantalla C's left column (SPEC "Pantalla C — System Detail": "Left
 * `StepsPanel` (steps, dependencies, AND credentials together, per
 * Felipe's decision) MUST be retractable via a full-height ~14px
 * vertical handle with `aria-expanded`/`aria-controls`, hidden via the
 * `hidden` attribute (not `opacity`/`width:0`); non-retractable and
 * stacked on mobile").
 *
 * Retract mechanism: the content region's visibility is the native
 * `hidden` boolean attribute (task 6.1's literal requirement — never a
 * CSS `opacity`/`width` trick, so assistive tech and `display` agree).
 * `expandido` defaults to `true`.
 *
 * "Non-retractable ... on mobile" is satisfied structurally, not via a
 * CSS override on the `hidden` attribute: the handle button itself is
 * only rendered visibly at the `md` breakpoint and up (`hidden md:flex`
 * — Tailwind's `hidden` utility class on the BUTTON, a different thing
 * from the native `hidden` ATTRIBUTE on the content region below). Since
 * `expandido` starts `true` and nothing on a small viewport can ever
 * flip it, mobile users structurally cannot collapse the panel — no
 * viewport-detection JS/media-query state needed. "Stacked on mobile" is
 * `flex-col` (this wrapper) vs. `md:flex-row` (steps beside main content,
 * wired by the page).
 */
export function StepsPanel({
  pasos,
  dependencias,
  credenciales,
}: {
  pasos: PasoSistema[];
  dependencias: DependenciaSistema[];
  credenciales: CredencialSistema[];
}) {
  const [expandido, setExpandido] = useState(true);
  const contenidoId = useId();

  return (
    <div className="flex flex-col border-b border-border-subtle md:w-72 md:shrink-0 md:flex-row md:border-r md:border-b-0">
      <button
        type="button"
        onClick={() => setExpandido((prev) => !prev)}
        aria-expanded={expandido}
        aria-controls={contenidoId}
        aria-label={expandido ? "Contraer panel de pasos" : "Expandir panel de pasos"}
        className="hidden w-3.5 shrink-0 items-center justify-center border-r border-border-subtle bg-surface text-text-muted transition-colors hover:bg-canvas focus:outline-none focus:ring-2 focus:ring-primary-100 md:flex"
      >
        <span aria-hidden="true" className="text-xs">
          {expandido ? "‹" : "›"}
        </span>
      </button>

      <div id={contenidoId} hidden={!expandido} className="flex w-full flex-col gap-6 p-4">
        <section>
          <h2 className="text-sm font-semibold text-text-strong">Pasos</h2>
          <StepChecklist pasos={pasos} />
        </section>

        <section>
          <h2 className="text-sm font-semibold text-text-strong">Dependencias</h2>
          <DependenciesList dependencias={dependencias} />
        </section>

        <section>
          <h2 className="text-sm font-semibold text-text-strong">Credenciales</h2>
          {credenciales.length === 0 ? (
            <p className="mt-2 text-sm text-text-muted">Este sistema no requiere credenciales.</p>
          ) : (
            <div className="mt-2 flex flex-col gap-3">
              {credenciales.map((credencial) => (
                <CredentialItem key={credencial.id} credencial={credencial} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
