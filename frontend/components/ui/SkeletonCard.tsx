/**
 * components/ui/SkeletonCard.tsx
 *
 * Cross-cutting loading-state primitive (SPEC §11.2 block states),
 * sized to stand in for a `MetricCard`/system row while data loads.
 * `motion-reduce:animate-none` — SPEC §11.2 "support ... `prefers-reduced-motion`".
 * Not wired to a live Suspense boundary in this PR (Pantalla A's data
 * comes from a fast in-memory mock, no real loading window yet); kept as
 * the shared primitive later async boundaries (D's chart, C's steps
 * panel) reuse instead of re-inventing.
 */
export function SkeletonCard() {
  return (
    <div
      aria-hidden="true"
      className="h-32 w-full animate-pulse rounded-2xl border border-border-subtle bg-canvas motion-reduce:animate-none"
    />
  );
}
