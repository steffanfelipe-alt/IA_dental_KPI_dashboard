import { describe, expect, it } from "vitest";
import { aplicarVentanaPeriodo, VENTANA_POR_PERIODO } from "./ventana";
import type { Metrica } from "@/lib/types";

/**
 * lib/data/ventana.test.ts
 *
 * WU-B1 task B1.7: `aplicarVentanaPeriodo` was extracted verbatim out of
 * `lib/data/panel.ts` into this file — `panel.test.ts` already covers the
 * happy-path window behavior end-to-end through `getPanel`, so this file
 * targets the short-serie fallback guard directly (never exercised by
 * `panel.test.ts`, whose fixtures all have the full 24 real points) to
 * confirm the extraction didn't change that guard's behavior.
 */
function metricaConSerie(valores: number[]): Metrica {
  return {
    slug: "metrica-test",
    nombre: "Métrica de prueba",
    unidad: "%",
    definicion: "fixture",
    porQueImporta: "fixture",
    tipo: "test",
    direccion: "mayor_mejor",
    valorActual: valores[valores.length - 1],
    valorAnterior: valores[0],
    objetivo: null,
    serie: valores.map((valor, indice) => ({
      periodo: `2026-${String(indice + 1).padStart(2, "0")}`,
      valor,
      proyectado: false,
    })),
    impactoScore: 0,
    vulnerabilidadScore: 0,
    sistemasAsociados: [],
  };
}

describe("aplicarVentanaPeriodo — short-serie fallback (post-extraction)", () => {
  it("cuando la serie real tiene menos puntos que la ventana pedida, cae al full-serie fallback (oldest real point como valorAnterior)", () => {
    const metrica = metricaConSerie([8, 10]); // solo 2 puntos reales
    const resultado = aplicarVentanaPeriodo(metrica, VENTANA_POR_PERIODO["6m"]); // pide 6

    expect(resultado.valorActual).toBe(10);
    expect(resultado.valorAnterior).toBe(8);
  });

  it("ventana válida (serie suficiente) sí recorta al primer punto REAL de la ventana pedida", () => {
    const metrica = metricaConSerie([1, 2, 3, 4, 5, 6]);
    const resultado = aplicarVentanaPeriodo(metrica, 3);

    expect(resultado.valorActual).toBe(6);
    expect(resultado.valorAnterior).toBe(4); // primer punto de slice(-3) = [4,5,6]
  });

  it("VENTANA_POR_PERIODO sigue exportando exactamente 3m/6m/12m tras la extracción", () => {
    expect(VENTANA_POR_PERIODO).toEqual({ "3m": 3, "6m": 6, "12m": 12 });
  });
});
