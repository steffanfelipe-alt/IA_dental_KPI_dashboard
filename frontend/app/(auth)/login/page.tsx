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

const loginSchema = z.object({
  email: z.string().min(1, "El email es obligatorio.").email("Ingresá un email válido."),
  password: z.string().min(1, "La contraseña es obligatoria."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(values: LoginFormValues) {
    setServerError(null);
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });

    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      const mensaje = isApiErrorEnvelope(body) ? body.error.mensaje : "No se pudo iniciar sesión.";
      setServerError(mensaje);
      return;
    }

    router.push("/");
    router.refresh();
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <p className="text-lg font-semibold text-ink-900">
        <span className="text-primary-600">AI</span> dental dashboard
      </p>

      <Card>
        <div className="space-y-6">
          <h1 className="text-2xl font-semibold text-ink-900">Iniciar sesión</h1>

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
              autoComplete="current-password"
              error={errors.password?.message}
              {...register("password")}
            />

            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Ingresando…" : "Ingresar"}
            </Button>
          </form>

          <p className="text-center text-sm text-ink-600">
            ¿No tenés cuenta?{" "}
            <Link href="/signup" className="font-medium text-primary-600 hover:text-primary-700">
              Creá una
            </Link>
          </p>
        </div>
      </Card>
    </main>
  );
}
