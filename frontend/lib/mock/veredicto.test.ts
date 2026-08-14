import { describe, expect, it } from "vitest";
import { MOCK_METRICAS } from "./veredicto";

/**
 * lib/mock/veredicto.test.ts
 *
 * U2 (task 3.5): `direccion` is a 1:1 transcription of
 * `BENCHMARKS_AR[kpi_id].mejor_es` (design "direccion transcription
 * (kpi_id → value)" table) — never inferred. This pins that transcription
 * so a future edit to `MOCK_METRICAS` can't silently drift from the
 * declared-direction table without failing a test.
 */
const DIRECCION_ESPERADA: Record<number, "mayor_mejor" | "menor_mejor" | null> = {
  1: "mayor_mejor",
  2: "menor_mejor",
  3: "mayor_mejor",
  4: "menor_mejor",
  5: "mayor_mejor",
  6: "mayor_mejor",
  7: "mayor_mejor",
  8: "mayor_mejor",
  9: "mayor_mejor",
  10: "mayor_mejor",
  11: null,
  12: "mayor_mejor",
  13: "mayor_mejor",
  14: null,
  15: "menor_mejor",
  16: null,
  17: null,
  18: null,
  19: "menor_mejor",
  20: null,
  21: "mayor_mejor",
};

const KPIS_SIN_DIRECCION_DECLARADA = [11, 14, 16, 17, 18, 20];

describe("MOCK_METRICAS direccion transcription", () => {
  it("matches BENCHMARKS_AR.mejor_es for every kpi_id (1-21)", () => {
    for (const metrica of MOCK_METRICAS) {
      expect(metrica.direccion).toBe(DIRECCION_ESPERADA[metrica.kpi_id]);
    }
  });

  it("never infers a direction for the 6 KPIs with no declared mejor_es (11, 14, 16, 17, 18, 20)", () => {
    for (const kpiId of KPIS_SIN_DIRECCION_DECLARADA) {
      const metrica = MOCK_METRICAS.find((m) => m.kpi_id === kpiId);
      expect(metrica).toBeDefined();
      expect(metrica?.direccion).toBeNull();
    }
  });

  it("declares a direction for every other KPI (1-21 minus the 6 undeclared)", () => {
    const conDireccion = MOCK_METRICAS.filter((m) => !KPIS_SIN_DIRECCION_DECLARADA.includes(m.kpi_id));
    for (const metrica of conDireccion) {
      expect(metrica.direccion).not.toBeNull();
    }
  });

  it("covers the full 21-KPI universe", () => {
    expect(MOCK_METRICAS.map((m) => m.kpi_id).sort((a, b) => a - b)).toEqual(
      Array.from({ length: 21 }, (_, i) => i + 1),
    );
  });
});
