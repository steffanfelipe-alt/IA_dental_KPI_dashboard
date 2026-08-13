import type { Direccion, Metrica } from "@/lib/types";

export type EstadoMetrica = "good" | "bad" | "flat";

export interface EvaluacionMetrica {
  estado: EstadoMetrica;
  /**
   * 0-100, direction-aware progress toward `objetivo`; `null` when
   * `objetivo` is `null` (SPEC §11.1: "si `objetivo === null`... no se
   * muestra `TargetBar`"). 100 means the objective is met or exceeded.
   * The exact formula isn't given verbatim in SPEC §11.1 (only the
   * `{ estado, avanceHaciaObjetivo }` return shape is) — this is the
   * one reasonable, direction-aware definition: for `mayor_mejor`, how
   * far `valorActual` has climbed toward `objetivo`; for `menor_mejor`,
   * how far it has dropped toward it.
   */
  avanceHaciaObjetivo: number | null;
}

/** SPEC §11.1: changes under this magnitude are noise, not signal. */
const UMBRAL_CAMBIO_RELEVANTE = 0.02;

type MetricaParaEvaluar = Pick<Metrica, "valorActual" | "valorAnterior" | "direccion" | "objetivo">;

/**
 * lib/semantics.ts::evaluarMetrica
 *
 * SPEC §11.1 — the SINGLE place `good | bad | flat` gets decided for a
 * metric. No other file computes this. Two traps this deliberately
 * guards against:
 *   1. Not every metric improves by going up — `direccion` decides what
 *      "mejorar" means, never assume `mayor_mejor`.
 *   2. Small deltas are noise: anything under the 2% relevance threshold
 *      is `flat` regardless of direction, so the dashboard doesn't paint
 *      the whole grid red/green on rounding noise.
 */
export function evaluarMetrica(metrica: MetricaParaEvaluar): EvaluacionMetrica {
  const { valorActual, valorAnterior, direccion, objetivo } = metrica;
  const delta = valorActual - valorAnterior;
  const base = Math.max(Math.abs(valorAnterior), 1);
  const cambioRelevante = Math.abs(delta) / base >= UMBRAL_CAMBIO_RELEVANTE;

  const avanceHaciaObjetivo = objetivo === null ? null : calcularAvanceHaciaObjetivo(valorActual, objetivo, direccion);

  if (!cambioRelevante) {
    return { estado: "flat", avanceHaciaObjetivo };
  }

  const mejorando = direccion === "mayor_mejor" ? delta > 0 : delta < 0;
  return { estado: mejorando ? "good" : "bad", avanceHaciaObjetivo };
}

function calcularAvanceHaciaObjetivo(valorActual: number, objetivo: number, direccion: Direccion): number {
  const objetivoCumplido = direccion === "mayor_mejor" ? valorActual >= objetivo : valorActual <= objetivo;
  if (objetivoCumplido) {
    return 100;
  }

  if (direccion === "mayor_mejor") {
    if (objetivo === 0) return 0;
    return clamp((valorActual / objetivo) * 100, 0, 100);
  }

  if (valorActual === 0) return 0;
  return clamp((objetivo / valorActual) * 100, 0, 100);
}

function clamp(valor: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, valor));
}
