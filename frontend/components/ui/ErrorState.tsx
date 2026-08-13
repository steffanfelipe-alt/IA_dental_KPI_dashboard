/**
 * components/ui/ErrorState.tsx
 *
 * Cross-cutting error-state primitive (SPEC §11.2 block states).
 * `role="alert"` so assistive tech announces it without extra wiring.
 * First real caller: `app/(app)/(dashboard)/panel/page.tsx` wraps
 * `getPanel` in a try/catch and renders this on failure.
 */
export function ErrorState({
  title = "Algo salió mal",
  description = "Intentá recargar la página en un momento.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center gap-1 rounded-2xl border border-state-bad/30 bg-state-bad/5 p-8 text-center">
      <p className="text-sm font-medium text-state-bad">{title}</p>
      <p className="text-xs text-text-muted">{description}</p>
    </div>
  );
}
