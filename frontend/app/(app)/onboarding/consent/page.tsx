"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

function ShieldIcon() {
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
      <path d="M12 3l7 3v6c0 4.5-3 8-7 9-4-1-7-4.5-7-9V6l7-3z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

/**
 * Spec "Consent Gate": one checkbox with a short DPA/BAA summary, blocking
 * progression until checked. No backend call happens here — consent is a
 * client-side gate before any clinic-scoped action starts.
 */
export default function ConsentPage() {
  const router = useRouter();
  const [accepted, setAccepted] = useState(false);

  function handleContinue() {
    router.push("/onboarding/clinica");
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <Card>
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-500">
              <ShieldIcon />
            </span>
            <h1 className="text-2xl font-semibold text-ink-900">Antes de empezar</h1>
          </div>

          <p className="text-sm text-ink-600">
            Vamos a procesar los datos de tu clínica (planillas, PDFs y fotos) para armar tu panel de control.
            Ese tratamiento se rige por nuestro Acuerdo de Procesamiento de Datos (DPA) y, cuando aplica, un
            Acuerdo de Asociado Comercial (BAA). Tus datos se usan solo para generar tu diagnóstico.
          </p>

          <label className="flex items-start gap-3 text-sm text-ink-900">
            <input
              type="checkbox"
              checked={accepted}
              onChange={(event) => setAccepted(event.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-ink-400/40 text-primary-600 focus:ring-2 focus:ring-primary-100"
            />
            <span>Entiendo y acepto el tratamiento de estos datos según el DPA/BAA de la plataforma.</span>
          </label>

          <Button type="button" onClick={handleContinue} disabled={!accepted}>
            Continuar <span aria-hidden="true">→</span>
          </Button>
        </div>
      </Card>
    </main>
  );
}
