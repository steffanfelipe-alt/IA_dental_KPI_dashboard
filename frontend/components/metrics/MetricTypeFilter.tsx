"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AGRUPACION_SEARCH_PARAM } from "@/lib/searchParams";

export type AgrupacionCatalogo = "embudo" | "categoria";

/**
 * components/metrics/MetricTypeFilter.tsx
 *
 * Pantalla B's "Embudo/Categoría" toggle (SPEC "Pantalla B — Catálogo":
 * "un catálogo agrupado por `nivelEmbudo` (default) con un toggle
 * Embudo/Categoría"). Design's file list names this component
 * `components/metrics/MetricTypeFilter.tsx` and its own prose calls it a
 * "type filter" among the sidebar-collapse/steps-retract/anclaje/
 * action-row-accordion client interactions — this PR keeps that exact
 * path and name even though it functionally toggles the SYSTEM catalog's
 * grouping key, not a metric type: it's the only component matching that
 * design entry, and SPEC/design name nothing else for this toggle.
 * Flagged as a naming judgment call in apply-progress, not silently
 * renamed.
 *
 * Same `?param=` search-param pattern as `PeriodPicker` (shareable by
 * URL, server component reads it directly) — a segmented two-button
 * control rather than a `<select>` since there are exactly two mutually
 * exclusive options (matches the wireframe's "toggle" wording, not a
 * dropdown).
 *
 * `AGRUPACION_SEARCH_PARAM` lives in `lib/searchParams.ts` (a plain, no
 * `"use client"` module), not defined here — see that file's header for
 * why: this component hit the exact same "runtime constant exported from
 * a `\"use client\"` file becomes an opaque reference when imported by a
 * Server Component" bug `PeriodPicker`'s `PERIODO_SEARCH_PARAM` had,
 * found and fixed together in this PR. Re-exported below so this file
 * stays a valid single import for both the key and the toggle.
 */
export { AGRUPACION_SEARCH_PARAM };
export function MetricTypeFilter({ value }: { value: AgrupacionCatalogo }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  function handleChange(next: AgrupacionCatalogo) {
    if (next === value) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set(AGRUPACION_SEARCH_PARAM, next);
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div role="group" aria-label="Agrupar catálogo por" className="inline-flex rounded-lg border border-border-subtle bg-surface p-0.5 text-sm">
      <button
        type="button"
        aria-pressed={value === "embudo"}
        onClick={() => handleChange("embudo")}
        className={`rounded-md px-3 py-1 font-medium transition-colors ${
          value === "embudo" ? "bg-canvas text-text-strong" : "text-text-muted hover:text-text-body"
        }`}
      >
        Embudo
      </button>
      <button
        type="button"
        aria-pressed={value === "categoria"}
        onClick={() => handleChange("categoria")}
        className={`rounded-md px-3 py-1 font-medium transition-colors ${
          value === "categoria" ? "bg-canvas text-text-strong" : "text-text-muted hover:text-text-body"
        }`}
      >
        Categoría
      </button>
    </div>
  );
}
