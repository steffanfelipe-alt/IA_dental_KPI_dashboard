import type { EstadoSistema } from "@/lib/types";

/**
 * components/systems/SystemStatusChip.tsx
 *
 * Small text pill for a system's `estado`, same `sys-*` color vocabulary
 * as `SystemBadge` (kept as a separate component because A3 rows show
 * both the ring AND the label, and Pantalla B/C need the label alone in
 * places the ring doesn't fit, e.g. a table row).
 *
 * `ESTADO_LABEL` is exported (PR5) so Pantalla B's panorama counts
 * (`sistemas/page.tsx`) reuse the exact same Spanish labels instead of a
 * second hand-typed copy of "Implementado"/"En proceso"/etc.
 */
export const ESTADO_LABEL: Record<EstadoSistema, string> = {
  implementado: "Implementado",
  en_proceso: "En proceso",
  sugerido: "Sugerido",
  disponible: "Disponible",
};

const ESTADO_CHIP_CLASS: Record<EstadoSistema, string> = {
  implementado: "bg-sys-live/10 text-sys-live",
  en_proceso: "bg-sys-progress/10 text-sys-progress",
  sugerido: "bg-sys-suggested/10 text-sys-suggested",
  disponible: "bg-sys-idle/10 text-sys-idle",
};

export function SystemStatusChip({ estado }: { estado: EstadoSistema }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${ESTADO_CHIP_CLASS[estado]}`}>
      {ESTADO_LABEL[estado]}
    </span>
  );
}
