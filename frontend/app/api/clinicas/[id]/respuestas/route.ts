import { NextResponse } from "next/server";
import { callApi } from "@/lib/bff/callApi";
import { errorResponse } from "@/lib/bff/errorResponse";
import type { RespuestasRequest } from "@/lib/types/api";

/**
 * PUT /api/clinicas/{id}/respuestas — proxies `PUT /onboarding/{id}/respuestas`
 * (D2/D5). The backend returns 204 No Content on success (see
 * `api/routers/onboarding.py`'s `guardar_respuestas`) — `callApi` returns
 * `undefined` for a 204 rather than attempting to parse an empty body, so
 * this mirrors that with its own empty `NextResponse`. `no-store`: this
 * mutates stored answers and must never be cached.
 */
export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const body = (await request.json()) as RespuestasRequest;

    await callApi<undefined>(`/onboarding/${id}/respuestas`, {
      method: "PUT",
      body,
      cache: { mode: "no-store" },
    });

    return new NextResponse(null, { status: 204 });
  } catch (error) {
    return errorResponse(error);
  }
}
