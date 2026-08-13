"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

export const PERIODO_SEARCH_PARAM = "periodo";

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
 * Not wired into any page yet in this PR (Pantalla A ships in a later
 * work unit) — created now alongside the rest of the shell per the
 * design's file list, ready for that page to render it in its header.
 */
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
