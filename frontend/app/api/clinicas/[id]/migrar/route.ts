import { NextResponse } from "next/server";
import { callApi } from "@/lib/bff/callApi";
import { errorResponse } from "@/lib/bff/errorResponse";
import type { MigrarResponse } from "@/lib/types/api";

// FormData bodies stream through the Node runtime; the Edge runtime
// doesn't support multipart forwarding at the size this endpoint allows
// (up to 20MB, see api/config.py's TAMANO_MAXIMO_ARCHIVO_BYTES).
export const runtime = "nodejs";

/**
 * POST /api/clinicas/{id}/migrar — proxies `POST /onboarding/{id}/migrar`
 * (D2). The incoming `FormData` is forwarded to FastAPI exactly as
 * received — never re-built, never given a manual Content-Type — so the
 * multipart boundary `fetch` derives from the FormData instance survives
 * the proxy hop intact (see callApi's `isMultipart` handling).
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const formData = await request.formData();

    const resultado = await callApi<MigrarResponse>(`/onboarding/${id}/migrar`, {
      method: "POST",
      body: formData,
      isMultipart: true,
    });

    return NextResponse.json(resultado);
  } catch (error) {
    return errorResponse(error);
  }
}
