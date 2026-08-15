import { describe, expect, it } from "vitest";
import { getSistema, getSistemas } from "./sistemas";
import { MOCK_METRICAS } from "@/lib/mock/panel";

/**
 * lib/data/sistemas.test.ts
 *
 * WU-B1 task B1.8: `getSistema` MUST return `impactoReal: null` on every
 * metric when the system has no `fechaImplementacion` (SPEC "System not
 * yet implemented" scenario) — nothing to measure since a date that
 * doesn't exist. Also covers `relacion` pass-through and the signed-delta
 * computation on an implemented system, per the "Front B —
 * relacion+impactoReal" design decision.
 */
const CLINICA_ID = "clinica-test";

describe("getSistema — impactoReal (Slice 2 WU-B1)", () => {
  it("impactoReal: null en TODAS las métricas cuando el sistema no tiene fechaImplementacion", async () => {
    const sistema = await getSistema(CLINICA_ID, "campana-reactivacion");
    expect(sistema).not.toBeNull();
    expect(sistema!.fechaImplementacion).toBeUndefined();
    for (const metrica of sistema!.metricas) {
      expect(metrica.impactoReal).toBeNull();
    }
  });

  it("delta con signo cuando el sistema SÍ tiene fechaImplementacion (menor_mejor invierte el signo)", async () => {
    const sistema = await getSistema(CLINICA_ID, "recordatorios-turnos");
    expect(sistema).not.toBeNull();
    expect(sistema!.fechaImplementacion).toBeDefined();

    const directa = sistema!.metricas.find((m) => m.slug === "tasa-no-show");
    const original = MOCK_METRICAS.find((m) => m.slug === "tasa-no-show");
    expect(directa?.impactoReal).toBe(-(original!.valorActual - 26));
  });

  it("relacion se propaga sin modificarse (directa vs. indirecta)", async () => {
    const sistema = await getSistema(CLINICA_ID, "recordatorios-turnos");
    const directa = sistema!.metricas.find((m) => m.slug === "tasa-no-show");
    const indirecta = sistema!.metricas.find((m) => m.slug === "tasa-cobro");

    expect(directa?.relacion).toBe("directa");
    expect(indirecta?.relacion).toBe("indirecta");
  });

  it("slug inexistente sigue devolviendo null (comportamiento Slice 1 sin cambios)", async () => {
    const sistema = await getSistema(CLINICA_ID, "no-existe");
    expect(sistema).toBeNull();
  });
});

describe("getSistemas — impactoReal por sistema (Slice 2 WU-B1)", () => {
  it("null para sistemas sin fechaImplementacion, no-null para sistemas implementados", async () => {
    const sistemas = await getSistemas(CLINICA_ID);

    const implementado = sistemas.find((s) => s.slug === "dashboard-financiero");
    expect(implementado?.metricas[0]?.impactoReal).not.toBeNull();

    const sinImplementar = sistemas.find((s) => s.slug === "seguimiento-presupuestos");
    expect(sinImplementar?.metricas[0]?.impactoReal).toBeNull();
  });
});
