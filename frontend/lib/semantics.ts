import type { Direccion, Metrica } from "@/lib/types";
import type { MetricaCalculada } from "@/lib/types/metricas";

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

/**
 * lib/semantics.ts::evaluarMetricaCalculada
 *
 * Veredicto adapter (design U2 "thin adapter deriving valorActual/
 * valorAnterior from the last 2 `serie` entries"). `MetricaCalculada`
 * (lib/types/metricas.ts) has no `valorActual`/`valorAnterior` of its
 * own — only a period `serie` — so this derives the pair `evaluarMetrica`
 * needs from the last two chronological points. `objetivo` is always
 * `null` here: Veredicto/Slice 1 has no real objective wired yet (see
 * `lib/mock/veredicto.ts`).
 *
 * Returns `null` (never a guessed state) when there's nothing safe to
 * evaluate: no declared `direccion` (spec "Declared Metric Direction" —
 * the 6 undeclared KPIs stay neutral, never inferred), no `serie`, or
 * fewer than 2 points to compare. Callers (e.g. `Sparkline`) render the
 * neutral/blue color on `null`.
 */
export function evaluarMetricaCalculada(
  metrica: Pick<MetricaCalculada, "serie" | "direccion">,
): EstadoMetrica | null {
  if (metrica.direccion === null || !metrica.serie) {
    return null;
  }

  const valores = Object.values(metrica.serie);
  if (valores.length < 2) {
    return null;
  }

  const valorAnterior = valores[valores.length - 2];
  const valorActual = valores[valores.length - 1];

  return evaluarMetrica({
    valorActual,
    valorAnterior,
    direccion: metrica.direccion,
    objetivo: null,
  }).estado;
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
