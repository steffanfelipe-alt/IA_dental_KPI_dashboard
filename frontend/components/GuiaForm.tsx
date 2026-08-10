"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, type SubmitErrorHandler, type SubmitHandler } from "react-hook-form";
import { isApiErrorEnvelope } from "@/lib/types/errors";
import type { GuiaResponse, PreguntaGuiaResponse } from "@/lib/types/api";
import { Button } from "@/components/ui/Button";
import { LoadingScreen } from "@/components/ui/LoadingScreen";
import { FormTextareaField } from "@/components/form/FormTextareaField";

/** Every answer is free text, keyed by question id — matches `RespuestasRequest.respuestas`. */
type FormValues = Record<string, string>;

interface Block {
  bloque: number;
  nombre_bloque: string;
  preguntas: PreguntaGuiaResponse[];
}

/**
 * Groups the flat `preguntas` list into blocks, in the order blocks first
 * appear in the response (no hardcoded block catalog — task 4.6: only ~11
 * of the possible 12 blocks are actually asked in onboarding, so the
 * block list is always derived from whatever the API returns).
 */
function groupByBlock(preguntas: PreguntaGuiaResponse[]): Block[] {
  const byBloque = new Map<number, Block>();
  for (const pregunta of preguntas) {
    const existing = byBloque.get(pregunta.bloque);
    if (existing) {
      existing.preguntas.push(pregunta);
    } else {
      byBloque.set(pregunta.bloque, {
        bloque: pregunta.bloque,
        nombre_bloque: pregunta.nombre_bloque,
        preguntas: [pregunta],
      });
    }
  }
  return Array.from(byBloque.values()).sort((a, b) => a.bloque - b.bloque);
}

/**
 * components/GuiaForm.tsx (task 4.6)
 *
 * The actual multi-block form (design D5): ONE `useForm` instance spans
 * every block. Step navigation only toggles which block is *visible* —
 * unmounted blocks' fields keep their values in RHF's internal state
 * (default `shouldUnregister: false`), so nothing is lost moving back and
 * forth. There is exactly one write: the "Finalizar" button on the last
 * block triggers the single `PUT respuestas` with the complete map.
 *
 * Exported (not the page's default) so task 5.4's test can drive it
 * directly with fixture `preguntas`, without needing to mock the initial
 * `GET /guia` fetch — mirrors `Upload.tsx` exporting `validateFiles` for
 * the same reason.
 */
export function GuiaFormBody({
  clinicaId,
  preguntas,
}: {
  clinicaId: string;
  preguntas: PreguntaGuiaResponse[];
}) {
  const router = useRouter();
  const blocks = useMemo(() => groupByBlock(preguntas), [preguntas]);
  const [blockIndex, setBlockIndex] = useState(0);
  const [banner, setBanner] = useState<string | null>(null);

  const defaultValues = useMemo<FormValues>(
    () => Object.fromEntries(preguntas.map((pregunta) => [pregunta.id, pregunta.respuesta ?? ""])),
    [preguntas],
  );

  const {
    register,
    handleSubmit,
    trigger,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ defaultValues });

  const currentBlock = blocks[blockIndex];
  const isLastBlock = blockIndex === blocks.length - 1;

  async function goNext() {
    setBanner(null);
    // Only núcleo (core) questions in the visible block gate navigation —
    // open-ended optional answers aren't force-validated per instruction.
    const requiredIds = currentBlock.preguntas.filter((pregunta) => pregunta.nucleo).map((pregunta) => pregunta.id);
    const valid = requiredIds.length === 0 || (await trigger(requiredIds));
    if (!valid) {
      return;
    }
    setBlockIndex((index) => Math.min(index + 1, blocks.length - 1));
  }

  function goBack() {
    setBanner(null);
    setBlockIndex((index) => Math.max(index - 1, 0));
  }

  const onValid: SubmitHandler<FormValues> = async (values) => {
    setBanner(null);
    const response = await fetch(`/api/clinicas/${clinicaId}/respuestas`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ respuestas: values }),
    });

    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      const mensaje = isApiErrorEnvelope(body) ? body.error.mensaje : "No se pudieron guardar las respuestas.";
      setBanner(mensaje);
      return;
    }

    // Spec/D7: estado MUST be refetched after every mutation.
    await fetch(`/api/clinicas/${clinicaId}/estado`, { cache: "no-store" });
    router.push(`/onboarding/${clinicaId}/estado`);
  };

  // If a núcleo field from a block that isn't currently visible fails
  // validation on the final submit, jump back to the earliest offending
  // block instead of silently failing with no visible error.
  const onInvalid: SubmitErrorHandler<FormValues> = (fieldErrors) => {
    const erroredIds = new Set(Object.keys(fieldErrors));
    const offendingIndex = blocks.findIndex((block) => block.preguntas.some((pregunta) => erroredIds.has(pregunta.id)));
    if (offendingIndex !== -1) {
      setBlockIndex(offendingIndex);
    }
    setBanner("Completá las preguntas obligatorias antes de finalizar.");
  };

  const progressPercent = blocks.length > 0 ? Math.round(((blockIndex + 1) / blocks.length) * 100) : 0;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <div className="w-full max-w-2xl space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm text-ink-600">
            <span>
              Bloque {blockIndex + 1} de {blocks.length}
            </span>
            <span>{progressPercent}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-primary-100">
            <div
              className="h-full rounded-full bg-primary-600 transition-all"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        <div className="w-full rounded-2xl border border-black/5 bg-white p-8 shadow-sm">
          <form onSubmit={handleSubmit(onValid, onInvalid)} noValidate className="space-y-6">
            {banner ? (
              <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
                {banner}
              </p>
            ) : null}

            <div>
              <h1 className="text-2xl font-semibold text-ink-900">{currentBlock.nombre_bloque}</h1>
            </div>

            <div className="space-y-5">
              {currentBlock.preguntas.map((pregunta) => (
                <FormTextareaField
                  key={pregunta.id}
                  id={pregunta.id}
                  label={pregunta.texto}
                  error={errors[pregunta.id]?.message as string | undefined}
                  {...register(pregunta.id, {
                    required: pregunta.nucleo ? "Esta respuesta es obligatoria." : false,
                  })}
                />
              ))}
            </div>

            <div className="flex items-center justify-between gap-3">
              {blockIndex > 0 ? (
                <button
                  type="button"
                  onClick={goBack}
                  className="rounded-xl px-4 py-2.5 text-sm font-medium text-ink-600 hover:text-ink-900"
                >
                  Atrás
                </button>
              ) : (
                <span />
              )}

              {/* Fixed-width wrapper: `Button` is `w-full` by design (fills its
                  parent), so constraining the parent here keeps these nav
                  buttons compact instead of stretching edge-to-edge like a
                  single-action page's submit button does. */}
              <div className="w-40">
                {isLastBlock ? (
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "Guardando…" : "Finalizar"}
                  </Button>
                ) : (
                  <Button type="button" onClick={goNext}>
                    Siguiente <span aria-hidden="true">→</span>
                  </Button>
                )}
              </div>
            </div>
          </form>
        </div>
      </div>
    </main>
  );
}

/**
 * Default export: fetches `GET /api/clinicas/{id}/guia` client-side, then
 * hands the result to `GuiaFormBody`. Kept separate from `GuiaFormBody`
 * so the form logic itself (task 5.4) is testable without mocking the
 * initial catalog fetch.
 */
export function GuiaForm({ clinicaId }: { clinicaId: string }) {
  const [data, setData] = useState<GuiaResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadGuia() {
      const response = await fetch(`/api/clinicas/${clinicaId}/guia`);
      const body: unknown = await response.json().catch(() => null);

      if (cancelled) {
        return;
      }

      if (!response.ok) {
        const mensaje = isApiErrorEnvelope(body) ? body.error.mensaje : "No se pudo cargar la guía.";
        setLoadError(mensaje);
        return;
      }

      setData(body as GuiaResponse);
    }

    void loadGuia();
    return () => {
      cancelled = true;
    };
  }, [clinicaId]);

  if (loadError) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
        <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
          {loadError}
        </p>
      </main>
    );
  }

  if (!data) {
    return <LoadingScreen />;
  }

  return <GuiaFormBody clinicaId={clinicaId} preguntas={data.preguntas} />;
}
