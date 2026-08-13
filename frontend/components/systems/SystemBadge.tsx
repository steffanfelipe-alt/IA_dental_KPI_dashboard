import type { EstadoSistema } from "@/lib/types";

/**
 * components/systems/SystemBadge.tsx
 *
 * Small ring badge encoding a system's `estado` by color (SPEC/wireframe
 * "ring encodes state"): solid ring for `implementado`/`en_proceso`,
 * dashed ring for `sugerido` (SPEC scenario "Suggested system shows
 * reason": "dashed arc, `sys-suggested` color"), thin idle ring for
 * `disponible`. This is the compact A3-row badge, distinct from Pantalla
 * B's `SystemMedallion` (PR5) — that one is the exhaustive catalog's
 * larger, standalone icon tile; this one sits inline in a system row.
 */
const ESTADO_RING_CLASS: Record<EstadoSistema, string> = {
  implementado: "border-sys-live text-sys-live",
  en_proceso: "border-sys-progress text-sys-progress",
  sugerido: "border-dashed border-sys-suggested text-sys-suggested",
  disponible: "border-sys-idle text-sys-idle",
};

/** `progresoPct: null` omits the center label entirely (used for the anchored group, where 0% isn't meaningful). */
export function SystemBadge({ estado, progresoPct }: { estado: EstadoSistema; progresoPct: number | null }) {
  return (
    <div
      aria-hidden="true"
      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 ${ESTADO_RING_CLASS[estado]}`}
    >
      {progresoPct !== null ? <span className="text-[10px] font-semibold tabular-nums">{progresoPct}%</span> : null}
    </div>
  );
}
