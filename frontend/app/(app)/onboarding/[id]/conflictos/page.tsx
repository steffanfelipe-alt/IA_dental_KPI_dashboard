"use client";

import { use, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { isApiErrorEnvelope } from "@/lib/types/errors";
import { Button } from "@/components/ui/Button";
import type { CandidatoConflicto, Conflicto, ResolverConflictoRequest } from "@/lib/types/api";

function sessionKey(clinicaId: string): string {
  return `onboarding:conflictos:${clinicaId}`;
}

function candidateSourceLabel(candidato: CandidatoConflicto): string {
  return candidato.archivo || candidato.fuente || "Fuente sin identificar";
}

/**
 * Candidate `valor` can be a scalar or a series/object (see
 * `CandidatoConflicto`) — this batch has no dedicated series visualization,
 * so a series just renders as its raw structure rather than being hidden.
 */
function formatCandidateValue(valor: unknown): string {
  if (valor === null || valor === undefined) {
    return "—";
  }
  if (typeof valor === "object") {
    try {
      return JSON.stringify(valor);
    } catch {
      return String(valor);
    }
  }
  return String(valor);
}

function safeParseConflictos(raw: string): Conflicto[] | null {
  try {
    return JSON.parse(raw) as Conflicto[];
  } catch {
    return null;
  }
}

type Choice = { kind: "candidate"; index: number } | { kind: "manual"; value: string };

/**
 * Spec "Conflict Resolution": one per-variable choice list, `POST
 * resolver-conflicto` per resolved variable, `estado` refetched only
 * after the last one, then routes to the guide.
 *
 * Data source: `conflictos_pendientes` is never persisted server-side —
 * `parser/pipeline.py`'s `procesar_migracion`/`resolver_conflicto` both
 * return it inline in their response body, with no corresponding GET
 * route (verified against `api/routers/onboarding.py`: only `migrar`,
 * `resolver-conflicto`, `guia`, `respuestas`, `estado` exist). This page
 * is a fresh navigation from `components/Upload.tsx` with no props, so
 * it reads the list that upload stashed in `sessionStorage` right before
 * navigating here, and clears it immediately (a direct reload/deep-link
 * with nothing stashed has no way to recover the list — the only place
 * that can regenerate it is a fresh upload).
 *
 * Candidate choice -> request shape (`parser/pipeline.py`'s
 * `resolver_conflicto`, Fase I8): picking a candidate sends
 * `{variable, candidatos: [elegido]}`, NOT `{variable, valor}` — the
 * `valor`-only path always built a bare scalar and silently destroyed
 * any series the candidate carried; `candidatos` preserves it via
 * `fusionar_candidatos`. A free-typed override sends `valor_manual`.
 */
export default function ConflictosPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: clinicaId } = use(params);
  const router = useRouter();

  // `null` = not read yet; `[]` = read but missing/invalid (redirect,
  // handled by the second effect below); non-empty = the real list.
  const [conflictos, setConflictos] = useState<Conflicto[] | null>(null);
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // Guards the sessionStorage read to a single run — same shape as
  // `useIdempotencyKey`'s mount-only guard.
  const initializedRef = useRef(false);

  // Split into two effects (read+setState here, redirect below) because
  // `react-hooks/set-state-in-effect` flags an effect that both calls
  // `setState` AND does something else (like `router.replace`) — verified
  // empirically: the single-branch "read once, setState once" shape below
  // (mirroring `useIdempotencyKey`) passes; adding a sibling
  // `router.replace` call to that same effect body does not, regardless
  // of whether it's an early return or an if/else.
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const key = sessionKey(clinicaId);
    const raw = sessionStorage.getItem(key);
    sessionStorage.removeItem(key);
    const parsed = raw ? safeParseConflictos(raw) : null;
    setConflictos(parsed ?? []);
  }, [clinicaId]);

  useEffect(() => {
    if (conflictos !== null && conflictos.length === 0) {
      router.replace(`/onboarding/${clinicaId}/upload`);
    }
  }, [conflictos, clinicaId, router]);

  function selectCandidate(variable: string, index: number) {
    setChoices((prev) => ({ ...prev, [variable]: { kind: "candidate", index } }));
  }

  function selectManual(variable: string, value: string) {
    setChoices((prev) => ({ ...prev, [variable]: { kind: "manual", value } }));
  }

  const allChosen =
    conflictos !== null &&
    conflictos.every((conflicto) => {
      const choice = choices[conflicto.variable];
      if (!choice) return false;
      return choice.kind === "candidate" || choice.value.trim().length > 0;
    });

  async function handleConfirm() {
    if (!conflictos) return;
    setSubmitting(true);
    setError(null);

    for (const conflicto of conflictos) {
      const choice = choices[conflicto.variable];
      const opciones = conflicto.opciones ?? [];
      const body: ResolverConflictoRequest =
        choice.kind === "manual"
          ? { variable: conflicto.variable, valor_manual: choice.value }
          : { variable: conflicto.variable, candidatos: [opciones[choice.index]] };

      const response = await fetch(`/api/clinicas/${clinicaId}/resolver-conflicto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const responseBody: unknown = await response.json().catch(() => null);

      if (!response.ok) {
        const mensaje = isApiErrorEnvelope(responseBody)
          ? responseBody.error.mensaje
          : `No se pudo resolver "${conflicto.variable}".`;
        setError(mensaje);
        setSubmitting(false);
        return;
      }
    }

    // Spec: "estado is refetched after the last one" — one refetch after
    // the loop, not per-choice.
    await fetch(`/api/clinicas/${clinicaId}/estado`, { cache: "no-store" });

    setSubmitting(false);
    router.push(`/onboarding/${clinicaId}/guia`);
  }

  // `null` (not read yet) or `[]` (missing/invalid — the redirect effect
  // above is about to navigate away) both render the same loading state.
  if (conflictos === null || conflictos.length === 0) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center p-8">
        <p className="text-sm text-ink-600">Cargando…</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <div className="w-full max-w-2xl space-y-6 rounded-2xl border border-black/5 bg-white p-8 shadow-sm">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-ink-900">Resolvamos algunas dudas</h1>
          <p className="text-sm text-ink-600">
            Encontramos valores distintos para {conflictos.length === 1 ? "esta variable" : "estas variables"}.
            Elegí cuál es correcto.
          </p>
        </div>

        {error ? (
          <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        ) : null}

        <ul className="space-y-6">
          {conflictos.map((conflicto) => {
            const opciones = conflicto.opciones ?? [];
            const choice = choices[conflicto.variable];

            return (
              <li key={conflicto.variable} className="space-y-3">
                <p className="text-sm font-medium text-ink-900">{conflicto.pregunta ?? conflicto.variable}</p>

                <div className="space-y-2">
                  {opciones.map((opcion, index) => {
                    const selected = choice?.kind === "candidate" && choice.index === index;
                    return (
                      <button
                        key={index}
                        type="button"
                        onClick={() => selectCandidate(conflicto.variable, index)}
                        className={`flex w-full flex-col items-start gap-0.5 rounded-xl border px-3 py-2.5 text-left text-sm transition-colors ${
                          selected ? "border-primary-500 bg-primary-50" : "border-ink-400/20 hover:border-primary-300"
                        }`}
                      >
                        <span className="font-medium text-ink-900">{formatCandidateValue(opcion.valor)}</span>
                        <span className="text-xs text-ink-400">{candidateSourceLabel(opcion)}</span>
                      </button>
                    );
                  })}

                  {conflicto.permite_valor_manual ? (
                    <div
                      className={`flex items-center rounded-xl border px-3 py-2 text-sm transition-colors ${
                        choice?.kind === "manual" ? "border-primary-500 bg-primary-50" : "border-ink-400/20"
                      }`}
                    >
                      <input
                        type="text"
                        placeholder="Otro valor…"
                        value={choice?.kind === "manual" ? choice.value : ""}
                        onChange={(event) => selectManual(conflicto.variable, event.target.value)}
                        className="w-full bg-transparent text-ink-900 placeholder:text-ink-400 focus:outline-none"
                      />
                    </div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>

        <Button type="button" onClick={handleConfirm} disabled={submitting || !allChosen}>
          {submitting ? "Guardando…" : "Confirmar y continuar"}
        </Button>
      </div>
    </main>
  );
}
