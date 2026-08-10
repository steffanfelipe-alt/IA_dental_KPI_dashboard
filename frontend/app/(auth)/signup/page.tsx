"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { isApiErrorEnvelope } from "@/lib/types/errors";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TextField } from "@/components/ui/TextField";

const signupSchema = z.object({
  email: z.string().min(1, "El email es obligatorio.").email("Ingresá un email válido."),
  password: z.string().min(6, "La contraseña debe tener al menos 6 caracteres."),
});

type SignupFormValues = z.infer<typeof signupSchema>;

export default function SignupPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SignupFormValues>({ resolver: zodResolver(signupSchema) });

  async function onSubmit(values: SignupFormValues) {
    setServerError(null);
    const response = await fetch("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });

    const body: unknown = await response.json().catch(() => null);

    if (!response.ok) {
      // D6: 409 (duplicate email) is a field-level error, everything
      // else is a generic banner.
      if (isApiErrorEnvelope(body)) {
        if (body.error.codigo === 409) {
          setError("email", { message: body.error.mensaje });
          return;
        }
        setServerError(body.error.mensaje);
        return;
      }
      setServerError("No se pudo crear la cuenta.");
      return;
    }

    const pendingConfirmation = Boolean((body as { pending_confirmation?: boolean } | null)?.pending_confirmation);
    router.push(pendingConfirmation ? "/check-email" : "/");
    router.refresh();
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <p className="text-lg font-semibold text-ink-900">
        <span className="text-primary-600">AI</span> dental dashboard
      </p>

      <Card>
        <div className="space-y-6">
          <h1 className="text-2xl font-semibold text-ink-900">Crear cuenta</h1>

          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
            {serverError ? (
              <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
                {serverError}
              </p>
            ) : null}

            <TextField
              id="email"
              label="Email"
              type="email"
              autoComplete="email"
              error={errors.email?.message}
              {...register("email")}
            />

            <TextField
              id="password"
              label="Contraseña"
              type="password"
              autoComplete="new-password"
              error={errors.password?.message}
              {...register("password")}
            />

            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Creando cuenta…" : "Crear cuenta"}
            </Button>
          </form>

          <p className="text-center text-sm text-ink-600">
            ¿Ya tenés cuenta?{" "}
            <Link href="/login" className="font-medium text-primary-600 hover:text-primary-700">
              Iniciá sesión
            </Link>
          </p>
        </div>
      </Card>
    </main>
  );
}
