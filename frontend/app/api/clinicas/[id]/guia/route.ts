import { NextResponse } from "next/server";
import { callApi } from "@/lib/bff/callApi";
import { errorResponse } from "@/lib/bff/errorResponse";
import type { GuiaResponse } from "@/lib/types/api";

/**
 * GET /api/clinicas/{id}/guia — proxies `GET /onboarding/{id}/guia` (D2/D7).
 * The question catalog is identical across users and clinics and doesn't
 * change within a session, so this is the one genuinely cacheable read in
 * the wizard — `next: { revalidate: 3600 }` instead of `no-store`.
 */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;

    const guia = await callApi<GuiaResponse>(`/onboarding/${id}/guia`, {
      method: "GET",
      cache: { mode: "revalidate", seconds: 3600 },
    });

    return NextResponse.json(guia);
  } catch (error) {
    return errorResponse(error);
  }
}
