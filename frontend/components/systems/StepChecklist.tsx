"use client";

import { useState } from "react";
import type { PasoSistema } from "@/lib/types";

/**
 * components/systems/StepChecklist.tsx
 *
 * Pantalla C (SPEC "Pantalla C — System Detail": "Steps are read-only
 * except type `accion_cliente`, which the clinic (end user) MAY check
 * off"). `lib/types.ts::PasoSistema.responsable` is SPEC §10 transcribed
 * verbatim (see that file's header) and its real enum is `"clinica" |
 * "agencia" | "automatico"` — there is no `"accion_cliente"` value
 * anywhere in the type contract. Treating `responsable === "clinica"` as
 * the type-safe equivalent of the SPEC scenario's `accion_cliente` (it is
 * the only value that names an action the clinic itself performs) is a
 * deliberate judgment call, not a silent guess — flagged in this PR's
 * apply-progress as a SPEC-prose vs. type-contract naming mismatch.
 *
 * `agencia`/`automatico` steps render as a fully read-only row (a plain
 * status dot + label, no `<input>` at all) rather than a disabled
 * checkbox, so "read-only" is enforced by the DOM shape itself, not just
 * a disabled attribute a client could flip via devtools.
 *
 * Checkoff state is in-memory only (design's data-flow: "client leaves
 * ... in-memory optimistic state, onToggle callbacks — Slice2 wires
 * PUT"), same pattern as `SystemsBlock`'s anclaje toggle.
 */
export function StepChecklist({ pasos }: { pasos: PasoSistema[] }) {
  const [completados, setCompletados] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(pasos.map((paso) => [paso.id, paso.completado])),
  );

  if (pasos.length === 0) {
    return <p className="mt-2 text-sm text-text-muted">Este sistema no tiene pasos definidos.</p>;
  }

  function toggle(id: string) {
    setCompletados((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  return (
    <ul className="mt-2 flex flex-col gap-2">
      {pasos.map((paso) => {
        const editable = paso.responsable === "clinica";
        const completado = completados[paso.id];
        const inputId = `paso-${paso.id}`;
        const textClass = completado ? "text-text-muted line-through" : "text-text-body";

        return (
          <li key={paso.id} className="flex items-start gap-2 text-sm">
            {editable ? (
              <>
                <input
                  type="checkbox"
                  id={inputId}
                  checked={completado}
                  onChange={() => toggle(paso.id)}
                  className="mt-0.5 h-4 w-4 shrink-0 rounded border-border-subtle text-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-100"
                />
                <label htmlFor={inputId} className={textClass}>
                  {paso.titulo}
                </label>
              </>
            ) : (
              <>
                <span
                  aria-hidden="true"
                  className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${completado ? "bg-state-good" : "bg-border-subtle"}`}
                />
                <span className={textClass}>{paso.titulo}</span>
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
