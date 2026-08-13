/**
 * components/ui/SectionHeading.tsx
 *
 * Shared block heading for a dashboard section (A1/A2/A3, and future B/C/D
 * blocks) — `text-strong` title + optional muted subtitle, extending the
 * existing `ui/` primitives (`Card`, `Button`, `IconCircle`) with the
 * `(dashboard)` token vocabulary instead of `ink-*`.
 */
export function SectionHeading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-lg font-semibold text-text-strong">{title}</h2>
      {subtitle ? <p className="text-sm text-text-muted">{subtitle}</p> : null}
    </div>
  );
}
