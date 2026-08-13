import { formatearNumero } from "@/lib/format";
import type { EstadoMetrica } from "@/lib/semantics";

/**
 * components/metrics/TargetBar.tsx
 *
 * Progress bar toward `Metrica.objetivo` (SPEC §11.1: "si `objetivo ===
 * null`... no se muestra `TargetBar`" — enforced by the caller, this
 * component always renders once given a non-null `objetivo`/
 * `avanceHaciaObjetivo`, it never re-checks null itself). Fill color
 * follows `estado` so the bar reads good/bad/flat consistently with the
 * rest of the card, not a fixed brand color.
 */
const ESTADO_BAR_CLASS: Record<EstadoMetrica, string> = {
  good: "bg-state-good",
  bad: "bg-state-bad",
  flat: "bg-state-flat",
};

interface TargetBarProps {
  avanceHaciaObjetivo: number;
  objetivo: number;
  unidad: string;
  estado: EstadoMetrica;
}

export function TargetBar({ avanceHaciaObjetivo, objetivo, unidad, estado }: TargetBarProps) {
  const pct = Math.round(avanceHaciaObjetivo);

  return (
    <div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-1.5 w-full overflow-hidden rounded-full bg-canvas"
      >
        <span className={`block h-full rounded-full ${ESTADO_BAR_CLASS[estado]}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1 text-xs tabular-nums text-text-muted">
        objetivo {formatearNumero(objetivo)} {unidad} · {pct}%
      </p>
    </div>
  );
}
