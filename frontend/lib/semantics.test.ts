import { describe, expect, it } from "vitest";
import { evaluarMetrica } from "./semantics";

function metrica(overrides: {
  valorActual: number;
  valorAnterior: number;
  direccion: "mayor_mejor" | "menor_mejor";
  objetivo?: number | null;
}) {
  return { objetivo: null, ...overrides };
}

describe("evaluarMetrica", () => {
  it("mayor_mejor + valor subiendo >2% → good", () => {
    const resultado = evaluarMetrica(metrica({ valorActual: 68, valorAnterior: 60, direccion: "mayor_mejor" }));
    expect(resultado.estado).toBe("good");
  });

  it("mayor_mejor + valor bajando >2% → bad", () => {
    const resultado = evaluarMetrica(metrica({ valorActual: 55, valorAnterior: 65, direccion: "mayor_mejor" }));
    expect(resultado.estado).toBe("bad");
  });

  it("menor_mejor + valor bajando >2% → good (menos es mejor)", () => {
    const resultado = evaluarMetrica(metrica({ valorActual: 15, valorAnterior: 20, direccion: "menor_mejor" }));
    expect(resultado.estado).toBe("good");
  });

  it("menor_mejor + valor subiendo >2% → bad (empeora)", () => {
    const resultado = evaluarMetrica(metrica({ valorActual: 25, valorAnterior: 20, direccion: "menor_mejor" }));
    expect(resultado.estado).toBe("bad");
  });

  it("cambio bajo el piso de 2% → flat, sin importar la dirección", () => {
    const mayorMejor = evaluarMetrica(metrica({ valorActual: 60.5, valorAnterior: 60, direccion: "mayor_mejor" }));
    const menorMejor = evaluarMetrica(metrica({ valorActual: 60.5, valorAnterior: 60, direccion: "menor_mejor" }));
    expect(mayorMejor.estado).toBe("flat");
    expect(menorMejor.estado).toBe("flat");
  });

  it("objetivo null → avanceHaciaObjetivo es null (no se muestra TargetBar)", () => {
    const resultado = evaluarMetrica(
      metrica({ valorActual: 68, valorAnterior: 60, direccion: "mayor_mejor", objetivo: null }),
    );
    expect(resultado.avanceHaciaObjetivo).toBeNull();
  });

  it("objetivo alcanzado o superado → avanceHaciaObjetivo es 100", () => {
    const resultado = evaluarMetrica(
      metrica({ valorActual: 70, valorAnterior: 60, direccion: "mayor_mejor", objetivo: 65 }),
    );
    expect(resultado.avanceHaciaObjetivo).toBe(100);
  });

  it("objetivo lejano → avanceHaciaObjetivo entre 0 y 100, direction-aware", () => {
    const resultado = evaluarMetrica(
      metrica({ valorActual: 30, valorAnterior: 20, direccion: "menor_mejor", objetivo: 10 }),
    );
    expect(resultado.avanceHaciaObjetivo).not.toBeNull();
    expect(resultado.avanceHaciaObjetivo as number).toBeGreaterThan(0);
    expect(resultado.avanceHaciaObjetivo as number).toBeLessThan(100);
  });
});
