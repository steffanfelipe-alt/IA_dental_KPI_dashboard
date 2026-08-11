import type { ReactNode } from "react";

/**
 * components/ui/Panel.tsx
 *
 * `Card` (`components/ui/Card.tsx`) is deliberately `max-w-sm`, sized for
 * narrow wizard-step forms — widening it in place would regress every
 * existing usage. `Panel` is a sibling primitive for unconstrained-width
 * surfaces (dashboard-style grids, fullscreen detail views) that reuses
 * the exact same design tokens (`primary-*`, `ink-*`) and surface styling
 * (`rounded-2xl`, `shadow-sm`) so it reads as the same design system.
 */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`w-full rounded-2xl border border-black/5 bg-white p-8 shadow-sm ${className}`.trim()}>
      {children}
    </div>
  );
}
