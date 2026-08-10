import { NextResponse } from "next/server";
import { callApi } from "@/lib/bff/callApi";
import { errorResponse } from "@/lib/bff/errorResponse";
import type { ResolverConflictoRequest, ResolverConflictoResponse } from "@/lib/types/api";

/**
 * POST /api/clinicas/{id}/resolver-conflicto — proxies
 * `POST /onboarding/{id}/resolver-conflicto` (D2). The backend returns an
 * untyped `dict[str, Any]` (see `api/routers/onboarding.py`'s docstring:
 * mirroring `resolver_conflicto`'s heterogeneous keys in a Pydantic model
 * would just desync from `parser/pipeline.py`) — `ResolverConflictoResponse`
 * is the same defensive hand-written type used for `migrar`. `no-store`:
 * this mutates stored variables, so the response must never be cached.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const body = (await request.json()) as ResolverConflictoRequest;

    const resultado = await callApi<ResolverConflictoResponse>(`/onboarding/${id}/resolver-conflicto`, {
      method: "POST",
      body,
      cache: { mode: "no-store" },
    });

    return NextResponse.json(resultado);
  } catch (error) {
    return errorResponse(error);
  }
}
