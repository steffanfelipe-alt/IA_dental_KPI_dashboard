import { redirect } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { fetchEstadoReadOnly } from "../layout";

function CheckIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-6 w-6"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

/**
 * Spec "Estado Refetch and Confirmation": renders only when
 * `estado.completo === true`. Backward redirects for the other two
 * states (migration not done / guide not finished) mirror
 * `conflictos/page.tsx` and `[id]/layout.tsx`'s guard comment — a Server
 * Component here has no pathname to compare against, but
 * `estado/page.tsx` knows its own identity just by being this file.
 *
 * Spec "Estado page links into the veredicto page": this page now offers
 * a CTA into `/onboarding/[id]/veredicto`, the diagnóstico/informe
 * surface built starting in this change's Phase 2.
 */
export default async function OnboardingEstadoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await fetchEstadoReadOnly(id);

  if (!result.ok) {
    redirect(result.status === 401 ? "/login" : "/");
  }

  const { estado } = result;

  if (!estado.migracion_completada) {
    redirect(`/onboarding/${id}/upload`);
  }

  if (!estado.completo) {
    redirect(`/onboarding/${id}/guia`);
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <Card>
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-500">
              <CheckIcon />
            </span>
            <h1 className="text-2xl font-semibold text-ink-900">¡Listo!</h1>
          </div>

          <p className="text-sm text-ink-600">
            Terminaste el onboarding. Ya tenemos todo lo que necesitábamos de tu clínica para seguir con el
            siguiente paso.
          </p>

          <Link
            href={`/onboarding/${id}/veredicto`}
            className="flex w-full items-center justify-center rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-700"
          >
            Ver veredicto
          </Link>
        </div>
      </Card>
    </main>
  );
}
