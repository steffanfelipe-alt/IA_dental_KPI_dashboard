"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { PERIODO_SEARCH_PARAM } from "@/lib/searchParams";

export interface PeriodoOption {
  value: string;
  label: string;
}

/**
 * components/shell/PeriodPicker.tsx
 *
 * SPEC §5 "Selector de períodos (header)": a range control that affects
 * the WHOLE screen (not a single card), implemented as the `?periodo=`
 * search param so state is shareable by URL and a server component can
 * read it directly (`getPanel(clinicaId, periodo)` — design's data flow).
 *
 * `PERIODO_SEARCH_PARAM` moved to `lib/searchParams.ts` in PR5 — this
 * file previously defined AND exported it itself, which broke
 * `panel/page.tsx`'s reading of `?periodo=` (see that module's header
 * for the full root-cause writeup: importing a runtime constant from a
 * `"use client"` file into a Server Component silently yields an opaque
 * reference, not the real value). Re-exported below so existing imports
 * of `PERIODO_SEARCH_PARAM` from this file keep working.
 */
export { PERIODO_SEARCH_PARAM };
export function PeriodPicker({ options, value }: { options: PeriodoOption[]; value: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  function handleChange(next: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set(PERIODO_SEARCH_PARAM, next);
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <select
      value={value}
      onChange={(event) => handleChange(event.target.value)}
      aria-label="Selector de período"
      className="rounded-lg border border-border-subtle bg-surface px-3 py-1.5 text-sm text-text-body focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
