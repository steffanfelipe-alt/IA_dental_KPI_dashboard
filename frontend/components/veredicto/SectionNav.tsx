/**
 * components/veredicto/SectionNav.tsx
 *
 * Spec "Top navigation switches between 3 sections": one entry per
 * section, icon + name, active entry highlighted. No icon library is
 * installed in this repo (confirmed in explore obs #64) — icons follow
 * the existing inline-SVG convention (`estado/page.tsx`'s `CheckIcon`,
 * `components/ui/LoadingScreen.tsx`'s `ToothbrushIcon`): 24x24 viewBox,
 * `currentColor` stroke, no fill.
 */

export type VeredictoSection = "metricas" | "diagnostico" | "proximos";

function MetricasIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
    >
      <path d="M4 20V10M12 20V4M20 20v-7" />
    </svg>
  );
}

function DiagnosticoIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
    >
      <path d="M6 3.5h9a1.5 1.5 0 0 1 1.5 1.5v14a1.5 1.5 0 0 1-1.5 1.5H6a1.5 1.5 0 0 1-1.5-1.5V5A1.5 1.5 0 0 1 6 3.5Z" />
      <path d="M8 8h6M8 12h6M8 16h3" />
    </svg>
  );
}

function ProximosPasosIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
    >
      <path d="M4 12h14M12 6l6 6-6 6" />
    </svg>
  );
}

const SECTIONS: { id: VeredictoSection; label: string; Icon: () => React.JSX.Element }[] = [
  { id: "metricas", label: "Métricas", Icon: MetricasIcon },
  { id: "diagnostico", label: "Diagnóstico", Icon: DiagnosticoIcon },
  { id: "proximos", label: "Próximos pasos", Icon: ProximosPasosIcon },
];

export function SectionNav({
  active,
  onChange,
}: {
  active: VeredictoSection;
  onChange: (section: VeredictoSection) => void;
}) {
  return (
    <nav className="flex items-center gap-2 border-b border-black/5">
      {SECTIONS.map(({ id, label, Icon }) => {
        const isActive = id === active;
        return (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            aria-current={isActive ? "true" : undefined}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
              isActive
                ? "border-primary-600 text-primary-600"
                : "border-transparent text-ink-600 hover:text-ink-900"
            }`}
          >
            <Icon />
            {label}
          </button>
        );
      })}
    </nav>
  );
}
