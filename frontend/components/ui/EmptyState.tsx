/**
 * components/ui/EmptyState.tsx
 *
 * Cross-cutting empty-state primitive (SPEC §11.2 block states) — a
 * dashed card so it reads as "nothing here yet", not an error.
 */
export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 rounded-2xl border border-dashed border-border-subtle bg-surface p-8 text-center">
      <p className="text-sm font-medium text-text-body">{title}</p>
      {description ? <p className="text-xs text-text-muted">{description}</p> : null}
    </div>
  );
}
