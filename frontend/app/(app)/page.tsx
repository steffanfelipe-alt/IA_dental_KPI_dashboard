"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

/**
 * Placeholder landing for the authenticated area. The onboarding wizard
 * (`app/(app)/onboarding/**`, design D4) lands in later PRs — this page
 * exists so `app/(app)/layout.tsx`'s D1d session gate has something to
 * guard in this PR, and so login/signup have a real, working redirect
 * target to land on after establishing a session.
 */
export default function AppHome() {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  async function handleLogout() {
    setLoggingOut(true);
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-2xl font-semibold text-zinc-900">Sesión iniciada</h1>
      <p className="max-w-md text-zinc-600">
        El asistente de onboarding todavía no está disponible en esta versión — vas a poder crear tu
        clínica y cargar tus datos acá en un próximo paso.
      </p>
      <button
        type="button"
        onClick={handleLogout}
        disabled={loggingOut}
        className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
      >
        {loggingOut ? "Cerrando sesión…" : "Cerrar sesión"}
      </button>
    </main>
  );
}
