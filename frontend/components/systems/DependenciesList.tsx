import Link from "next/link";
import type { DependenciaSistema } from "@/lib/types";

/**
 * components/systems/DependenciesList.tsx
 *
 * Pantalla C's blocking-dependencies list, part of `StepsPanel`
 * (task 6.4). Read-only — no checkoff here, unlike `StepChecklist`;
 * dependencies resolve elsewhere (another system's own progress), this
 * only reports their `cumplida` state.
 *
 * TODO(felpa): SPEC §13 open item 2 — "page-3 sketch left-column items
 * beyond 'dependencias bloqueantes' (illegible)". Only the blocking-
 * dependencies list itself (`DependenciaSistema[]`) is implemented here;
 * revisit once Felipe can confirm what else that sketch column showed.
 */
export function DependenciesList({ dependencias }: { dependencias: DependenciaSistema[] }) {
  if (dependencias.length === 0) {
    return <p className="mt-2 text-sm text-text-muted">Sin dependencias.</p>;
  }

  return (
    <ul className="mt-2 flex flex-col gap-2">
      {dependencias.map((dependencia) => (
        <li key={dependencia.id} className="flex items-start gap-2 text-sm">
          <span
            aria-hidden="true"
            className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dependencia.cumplida ? "bg-state-good" : "bg-state-bad"}`}
          />
          <div className="min-w-0">
            <p className={dependencia.cumplida ? "text-text-body" : "text-text-strong"}>
              {dependencia.titulo}
              {dependencia.requerida ? <span className="ml-1 text-xs text-state-bad">(requerida)</span> : null}
            </p>
            {dependencia.sistemaSlug ? (
              <Link href={`/sistemas/${dependencia.sistemaSlug}`} className="text-xs text-primary-600 hover:underline">
                Ver sistema
              </Link>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
