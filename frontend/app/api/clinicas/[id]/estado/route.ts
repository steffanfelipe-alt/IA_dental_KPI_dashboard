import { NextResponse } from "next/server";
import { callApi } from "@/lib/bff/callApi";
import { errorResponse } from "@/lib/bff/errorResponse";
import type { EstadoResponse } from "@/lib/types/api";

/**
 * GET /api/clinicas/{id}/estado — proxies `GET /onboarding/{id}/estado`
 * (D2/D7). Always `no-store`: the spec requires this to be refetched
 * after every mutation (upload, resolve-conflict, save-answers), so a
 * cached read would silently violate that contract.
 */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;

    const estado = await callApi<EstadoResponse>(`/onboarding/${id}/estado`, {
      method: "GET",
      cache: { mode: "no-store" },
    });

    return NextResponse.json(estado);
  } catch (error) {
    return errorResponse(error);
  }
}
