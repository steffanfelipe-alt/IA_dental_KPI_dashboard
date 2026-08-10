import { redirect } from "next/navigation";
import { GuiaForm } from "@/components/GuiaForm";
import { fetchEstadoReadOnly } from "../layout";

/**
 * Task 4.6. Thin async Server Component that awaits the dynamic `[id]`
 * param and hands it to the client component doing the actual work —
 * same split as `[id]/upload/page.tsx`. Guards backward to `/upload`
 * when `migracion_completada` isn't true yet, same shape as
 * `conflictos/page.tsx` and `estado/page.tsx`'s guards — flagged as a
 * gap by the sibling batch that built those two pages.
 */
export default async function GuiaPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await fetchEstadoReadOnly(id);

  if (!result.ok) {
    redirect(result.status === 401 ? "/login" : "/");
  }

  if (!result.estado.migracion_completada) {
    redirect(`/onboarding/${id}/upload`);
  }

  return <GuiaForm clinicaId={id} />;
}
