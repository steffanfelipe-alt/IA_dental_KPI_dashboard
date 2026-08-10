/**
 * lib/bff/errorResponse.ts
 *
 * Converts whatever `callApi` threw into the same `NextResponse` shape
 * for every Route Handler — keeps the `{error:{codigo,mensaje,detalle}}`
 * envelope (D6) intact all the way from FastAPI through to the browser.
 */

import { NextResponse } from "next/server";
import { ApiError } from "@/lib/types/errors";

export function errorResponse(error: unknown): NextResponse {
  if (error instanceof ApiError) {
    return NextResponse.json(
      { error: { codigo: error.codigo, mensaje: error.message, detalle: error.detalle } },
      { status: error.codigo },
    );
  }
  // Defensive fallback — callApi always throws ApiError, but never let an
  // unexpected exception (e.g. a JSON.parse failure on the request body)
  // leak internals to the client.
  return NextResponse.json(
    { error: { codigo: 500, mensaje: "Error inesperado del servidor." } },
    { status: 500 },
  );
}
