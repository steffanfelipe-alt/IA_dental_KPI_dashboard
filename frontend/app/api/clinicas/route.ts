import { NextResponse } from "next/server";
import { callApi } from "@/lib/bff/callApi";
import { errorResponse } from "@/lib/bff/errorResponse";
import type { ClinicaResponse, CrearClinicaRequest } from "@/lib/types/api";

/**
 * POST /api/clinicas — proxies `POST /clinicas` (D2). Forwards the
 * client-generated `Idempotency-Key` header as-is (D3) so a retried
 * submit with the same key returns the already-created clinica instead
 * of a duplicate — see `api/routers/clinicas.py`. The header is optional
 * on the backend; when absent, behavior is an ordinary create.
 */
export async function POST(request: Request) {
  try {
    const body = (await request.json()) as CrearClinicaRequest;
    const idempotencyKey = request.headers.get("Idempotency-Key");

    const clinica = await callApi<ClinicaResponse>("/clinicas", {
      method: "POST",
      body,
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
    });

    return NextResponse.json(clinica, { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}
