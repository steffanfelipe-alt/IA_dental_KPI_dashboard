import { redirect } from "next/navigation";
import { fetchEstadoReadOnly } from "../layout";
import { Veredicto } from "@/components/veredicto/Veredicto";
import { MOCK_DIAGNOSTICO, MOCK_INFORME, MOCK_METRICAS } from "@/lib/mock/veredicto";

/**
 * Server guard mirrors `estado/page.tsx`: reuse `fetchEstadoReadOnly` and
 * the same backward-redirect chain (`/upload` if migration isn't done,
 * `/guia` if onboarding isn't complete) before rendering. Spec "All
 * content is mock-data-driven": this page imports the mock fixtures
 * server-side and passes them as props to the client shell — no fetch to
 * `/diagnostico` or `/informe` happens in this change (design "Server
 * page loads mock, passes as props": swapping in real data later is a
 * localized diff of these 3 imports for 2 fetches, no component churn).
 */
export default async function OnboardingVeredictoPage({ params }: { params: Promise<{ id: string }> }) {
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

  return <Veredicto diagnostico={MOCK_DIAGNOSTICO} informe={MOCK_INFORME} metricas={MOCK_METRICAS} />;
}
