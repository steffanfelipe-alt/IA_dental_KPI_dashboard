"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { isApiErrorEnvelope } from "@/lib/types/errors";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TextField } from "@/components/ui/TextField";
import { useIdempotencyKey } from "@/lib/hooks/useIdempotencyKey";
import type { ClinicaResponse } from "@/lib/types/api";

const clinicaSchema = z.object({
  nombre: z.string().min(1, "El nombre de la clínica es obligatorio."),
});

type ClinicaFormValues = z.infer<typeof clinicaSchema>;

/**
 * Spec "Clinic Creation With Idempotency": `Idempotency-Key` comes from
 * `useIdempotencyKey` (D3 — generated post-mount, never in the render
 * body) and is forwarded as a header to `POST /api/clinicas`, which the
 * BFF route copies onto the FastAPI call. The submit button stays
 * disabled until the key exists so a resubmit always carries the same key.
 */
export default function ClinicaPage() {
  const router = useRouter();
  const idempotencyKey = useIdempotencyKey();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ClinicaFormValues>({ resolver: zodResolver(clinicaSchema) });

  async function onSubmit(values: ClinicaFormValues) {
    setServerError(null);
    const response = await fetch("/api/clinicas", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
      },
      body: JSON.stringify(values),
    });

    const body: unknown = await response.json().catch(() => null);

    if (!response.ok) {
      const mensaje = isApiErrorEnvelope(body) ? body.error.mensaje : "No se pudo crear la clínica.";
      setServerError(mensaje);
      return;
    }

    const clinica = body as ClinicaResponse;
    router.push(`/onboarding/${clinica.id}/upload`);
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <Card>
        <div className="space-y-6">
          <h1 className="text-2xl font-semibold text-ink-900">Tu clínica</h1>
          <p className="text-sm text-ink-600">Contanos el nombre de tu clínica para empezar.</p>

          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
            {serverError ? (
              <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
                {serverError}
              </p>
            ) : null}

            <TextField
              id="nombre"
              label="Nombre de la clínica"
              type="text"
              autoComplete="organization"
              error={errors.nombre?.message}
              {...register("nombre")}
            />

            <Button type="submit" disabled={isSubmitting || !idempotencyKey}>
              {isSubmitting ? "Creando…" : "Continuar"}
            </Button>
          </form>
        </div>
      </Card>
    </main>
  );
}
