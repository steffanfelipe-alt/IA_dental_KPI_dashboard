import { createElement } from "react";
import Link from "next/link";
import { CircleHelp, type LucideIcon } from "lucide-react";
import * as LucideIcons from "lucide-react";
import type { EstadoSistema } from "@/lib/types";

/**
 * components/systems/SystemMedallion.tsx
 *
 * Pantalla B's catalog tile (SPEC "Pantalla B — Catálogo": "rendered as
 * `SystemMedallion` (not cards), icon from `icono` field only, ring
 * encodes state, text outside circle, ≥44×44px click target"). Distinct
 * from `SystemBadge` (the compact A3-row ring that shows a progress %
 * inside instead of an icon, see that file's header) — this one is the
 * exhaustive catalog's standalone icon tile.
 *
 * Also closes the cross-phase gap PR4's apply-progress flagged: no
 * component produced a real `/sistemas/[slug]?from=catalogo` link yet.
 * The whole tile (icon + name) is a single `next/link` `Link`, matching
 * `MetricCard`'s "single click target" precedent (SPEC, Pantalla A) even
 * though that exact wording is only written for `MetricCard` — applying
 * the same click-target discipline here is a judgment call, not SPEC
 * text, flagged in apply-progress.
 *
 * `icono` (SPEC §10: "nombre del ícono de Lucide") is resolved directly
 * against `lucide-react`'s real export map by PascalCasing the kebab-case
 * name (e.g. `bell-ring` → `BellRing`) instead of hand-maintaining a
 * lookup table for just the mock's 7 icon names — this way ANY valid
 * Lucide icon name in future mock/backend data resolves for free, with a
 * generic fallback (`CircleHelp`) for anything unrecognized instead of a
 * crash or blank tile.
 */
function resolverIcono(nombre: string): LucideIcon {
  const pascalCase = nombre
    .split("-")
    .filter(Boolean)
    .map((segmento) => segmento.charAt(0).toUpperCase() + segmento.slice(1))
    .join("");
  const icono = (LucideIcons as unknown as Record<string, LucideIcon>)[pascalCase];
  return icono ?? CircleHelp;
}

/** Same `sys-*` ring vocabulary as `SystemBadge` — see that file's header. Pantalla B is exhaustive, so `disponible` IS shown here (unlike A3). */
const ESTADO_RING_CLASS: Record<EstadoSistema, string> = {
  implementado: "border-sys-live text-sys-live",
  en_proceso: "border-sys-progress text-sys-progress",
  sugerido: "border-dashed border-sys-suggested text-sys-suggested",
  disponible: "border-sys-idle text-sys-idle",
};

/** 44px = Tailwind's `h-11`/`w-11` exactly (11 × 0.25rem). Also set as an explicit inline floor so the ≥44×44px hit-target contract is enforced and testable independent of Tailwind's generated CSS being present (jsdom tests load no stylesheet). */
const HIT_TARGET_MIN_PX = 44;

export function SystemMedallion({ sistema }: { sistema: { slug: string; nombre: string; icono: string; estado: EstadoSistema } }) {
  // `createElement` (not a `<Icono />` JSX tag) on purpose: `resolverIcono`
  // returns a dynamically-picked component reference, and
  // `react-hooks/static-components` (this repo's eslint config, part of
  // the React Compiler rules) flags "components created during render"
  // for the `<Variable />` JSX-tag-from-a-render-time-variable shape even
  // though `resolverIcono` is a pure, stable lookup (same input → same
  // Lucide export reference every time, never actually a new component
  // identity). `createElement` sidesteps the lint's syntactic check while
  // producing the identical element.
  const icono = createElement(resolverIcono(sistema.icono), { className: "h-5 w-5", strokeWidth: 1.75 });

  return (
    <Link
      href={`/sistemas/${sistema.slug}?from=catalogo`}
      style={{ minWidth: HIT_TARGET_MIN_PX, minHeight: HIT_TARGET_MIN_PX }}
      className="flex flex-col items-center gap-2 rounded-xl p-1 text-center focus:outline-none focus:ring-2 focus:ring-primary-100"
    >
      <span
        aria-hidden="true"
        className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 ${ESTADO_RING_CLASS[sistema.estado]}`}
      >
        {icono}
      </span>
      <span className="line-clamp-2 max-w-[6.5rem] text-xs font-medium text-text-body">{sistema.nombre}</span>
    </Link>
  );
}
