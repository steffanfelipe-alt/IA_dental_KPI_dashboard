"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

function ClockIcon() {
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
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}

function SparkleIcon() {
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
      <path d="M12 4v4M12 16v4M4 12h4M16 12h4M6.5 6.5l2 2M15.5 15.5l2 2M6.5 17.5l2-2M15.5 8.5l2-2" />
    </svg>
  );
}

/**
 * Welcome landing for the authenticated area (design D4). "Continuar"
 * starts the onboarding wizard at its first step, the consent gate.
 */
export default function AppHome() {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  function handleContinue() {
    router.push("/onboarding/consent");
  }

  async function handleLogout() {
    setLoggingOut(true);
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <Card>
        <div className="space-y-6">
          <div>
            <p className="text-ink-900">Te damos la bienvenida a</p>
            <p className="text-2xl font-semibold text-ink-900">
              <span className="text-primary-600">AI</span> dental dashboard!
            </p>
          </div>

          <ul className="space-y-4">
            <li className="flex gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-500">
                <ClockIcon />
              </span>
              <div>
                <p className="text-sm font-medium text-ink-900">Esto te va a llevar ~15 min.</p>
                <p className="text-sm text-ink-600">Podés pausar y retomar cuando quieras.</p>
              </div>
            </li>
            <li className="flex gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-500">
                <SparkleIcon />
              </span>
              <div>
                <p className="text-sm font-medium text-ink-900">Vamos a armar tu panel de control</p>
                <p className="text-sm text-ink-600">en base a tus datos reales.</p>
              </div>
            </li>
          </ul>

          <Button type="button" onClick={handleContinue}>
            Continuar <span aria-hidden="true">→</span>
          </Button>
        </div>
      </Card>

      <button
        type="button"
        onClick={handleLogout}
        disabled={loggingOut}
        className="text-sm font-medium text-ink-600 hover:text-ink-900 disabled:opacity-50"
      >
        {loggingOut ? "Cerrando sesión…" : "Cerrar sesión"}
      </button>
    </main>
  );
}
