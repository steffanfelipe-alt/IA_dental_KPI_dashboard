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
  12: "mayor_mejor",
  13: "mayor_mejor",
  15: "menor_mejor",
  16: null,
  19: "menor_mejor",
  21: "mayor_mejor",
};

const KPI_UNIVERSE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 16, 19, 21];

const KPIS_SIN_DIRECCION_DECLARADA = [16];

describe("MOCK_METRICAS direccion transcription", () => {
  it("matches BENCHMARKS_AR.mejor_es for every kpi_id (16-KPI universe, ids not renumbered after Slice 2 prune)", () => {
    for (const metrica of MOCK_METRICAS) {
      expect(metrica.direccion).toBe(DIRECCION_ESPERADA[metrica.kpi_id]);
    }
  });

  it("never infers a direction for the 1 KPI with no declared mejor_es (16)", () => {
    for (const kpiId of KPIS_SIN_DIRECCION_DECLARADA) {
      const metrica = MOCK_METRICAS.find((m) => m.kpi_id === kpiId);
      expect(metrica).toBeDefined();
      expect(metrica?.direccion).toBeNull();
    }
  });

  it("declares a direction for every other KPI (16-KPI universe minus the 1 undeclared)", () => {
    const conDireccion = MOCK_METRICAS.filter((m) => !KPIS_SIN_DIRECCION_DECLARADA.includes(m.kpi_id));
    for (const metrica of conDireccion) {
      expect(metrica.direccion).not.toBeNull();
    }
  });

  it("covers the full 16-KPI universe (ids not renumbered after Slice 2 prune)", () => {
    expect(MOCK_METRICAS.map((m) => m.kpi_id).sort((a, b) => a - b)).toEqual(KPI_UNIVERSE);
  });
});
