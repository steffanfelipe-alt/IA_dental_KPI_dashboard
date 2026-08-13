// @vitest-environment jsdom
/**
 * app/(app)/(dashboard)/navigation-integration.test.tsx
 *
 * Task 7.5: "Integration tests: exercise A/B/C/D screens together on the
 * mocks, verify `?from=`/`?periodo=` propagate correctly across
 * navigation." The A/B/C/D pages themselves are async Server Components
 * gated behind `resolverClinicaIdActual()` → `next/headers`' `cookies()`,
 * which throws outside a real request context — rendering the full pages
 * directly in vitest/jsdom isn't a meaningful integration boundary (see
 * this PR's apply-progress for the judgment call). Instead this file
 * exercises the actual CROSS-SCREEN CONTRACT at the seam that matters:
 * every component that EMITS a `/sistemas/[slug]?from=...` or
 * `/metricas/[slug]` link, plus the one place (Pantalla C) that CONSUMES
 * `?from=`, plus the one place (Pantalla A) that owns `?periodo=`. Each
 * page's own loader/error/notFound wiring is covered by this PR's manual
 * runtime harness pass (see apply-progress), same as PR3/PR4 did for
 * their own pages.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { resolveSistemaBreadcrumb } from "@/lib/nav";
import { SystemsBlock } from "@/components/systems/SystemsBlock";
import { SystemMedallion } from "@/components/systems/SystemMedallion";
import { MetricCard } from "@/components/metrics/MetricCard";
import { ActionsTable } from "@/components/systems/ActionsTable";
import { PeriodPicker } from "@/components/shell/PeriodPicker";
import { MetricTypeFilter } from "@/components/metrics/MetricTypeFilter";
import { PERIODO_SEARCH_PARAM, AGRUPACION_SEARCH_PARAM } from "@/lib/searchParams";
import type { AccionSobreMetrica, Metrica, Sistema } from "@/lib/types";

const pushMock = vi.fn();
const searchParamsMock = { toString: () => "" };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/panel",
  useSearchParams: () => searchParamsMock,
}));

/** Same jsdom/ResponsiveContainer gotcha as `MetricCard.test.tsx` — see that file's header. */
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
}));

function sistema(overrides: Partial<Sistema> = {}): Sistema {
  return {
    slug: "sistema-test",
    nombre: "Sistema de prueba",
    descripcionCorta: "Descripción corta.",
    icono: "bell-ring",
    nivelEmbudo: "retencion",
    categoria: "Comunicación",
    estado: "en_proceso",
    progresoPct: 40,
    sugeridoPorVeredicto: false,
    anclado: false,
    pasos: [],
    dependencias: [],
    credenciales: [],
    metricas: [],
    ...overrides,
  };
}

function metrica(overrides: Partial<Metrica> = {}): Metrica {
  return {
    slug: "metrica-test",
    nombre: "Métrica de prueba",
    unidad: "%",
    definicion: "Definición.",
    porQueImporta: "Importa porque sí.",
    tipo: "conversion",
    direccion: "mayor_mejor",
    valorActual: 10,
    valorAnterior: 8,
    objetivo: 20,
    serie: [
      { periodo: "2026-01", valor: 8, proyectado: false },
      { periodo: "2026-02", valor: 10, proyectado: false },
    ],
    impactoScore: 5,
    vulnerabilidadScore: 5,
    sistemasAsociados: [],
    ...overrides,
  };
}

describe("Cross-screen navigation contract (task 7.5)", () => {
  afterEach(cleanup);

  describe("A (panel) → C (system detail): SystemsBlock emits ?from=panel", () => {
    it("links an A3 main-list system to /sistemas/[slug]?from=panel", () => {
      render(<SystemsBlock sistemas={[sistema({ slug: "campana-reactivacion", nombre: "Campaña de reactivación", estado: "en_proceso" })]} />);

      // Accessible name of the whole card link concatenates its visible text (name + status chip), so match by substring.
      const link = screen.getByRole("link", { name: /Campaña de reactivación/ }) as HTMLAnchorElement;
      expect(link.getAttribute("href")).toBe("/sistemas/campana-reactivacion?from=panel");
    });

    it("links an anchored (A3-bis) system's name to /sistemas/[slug]?from=panel, kept separate from the Desanclar button", () => {
      render(<SystemsBlock sistemas={[sistema({ slug: "programa-referidos", nombre: "Programa de referidos", estado: "disponible", anclado: true })]} />);

      const link = screen.getByRole("link", { name: "Programa de referidos" }) as HTMLAnchorElement;
      expect(link.getAttribute("href")).toBe("/sistemas/programa-referidos?from=panel");
      // Desanclar stays a real, separate <button> — never nested inside the <a> (invalid HTML).
      const boton = screen.getByRole("button", { name: "Desanclar Programa de referidos" });
      expect(boton.tagName).toBe("BUTTON");
      expect(link.contains(boton)).toBe(false);
    });
  });

  describe("B (catálogo) → C (system detail): SystemMedallion emits ?from=catalogo", () => {
    it("links a catalog tile to /sistemas/[slug]?from=catalogo", () => {
      render(<SystemMedallion sistema={sistema({ slug: "dashboard-financiero", nombre: "Dashboard financiero", estado: "implementado" })} />);

      const link = screen.getByRole("link", { name: "Dashboard financiero" }) as HTMLAnchorElement;
      expect(link.getAttribute("href")).toBe("/sistemas/dashboard-financiero?from=catalogo");
    });
  });

  describe("D (metric detail) → C (system detail): ActionsTable's pre-existing ?from=metrica", () => {
    it("still links to /sistemas/[slug]?from=metrica (PR3 behavior, unaffected by this PR's changes)", () => {
      const accion: AccionSobreMetrica = {
        sistema: { slug: "seguimiento-presupuestos", nombre: "Seguimiento de presupuestos", estado: "sugerido" },
        impactoEstimadoPct: 12.5,
        valorProyectado: 65,
        porQueServiria: "Porque sí.",
      };
      render(<ActionsTable acciones={[accion]} />);

      const link = screen.getByRole("link", { name: "Seguimiento de presupuestos" }) as HTMLAnchorElement;
      expect(link.getAttribute("href")).toBe("/sistemas/seguimiento-presupuestos?from=metrica");
    });
  });

  describe("C (system detail): resolveSistemaBreadcrumb consumes every ?from= value the app emits", () => {
    it("resolves 'panel' (from SystemsBlock, A) to the Panel prioritario breadcrumb", () => {
      expect(resolveSistemaBreadcrumb("panel")).toEqual({ label: "Panel prioritario", href: "/panel" });
    });

    it("resolves 'catalogo' (from SystemMedallion, B) to the Sistemas breadcrumb", () => {
      expect(resolveSistemaBreadcrumb("catalogo")).toEqual({ label: "Sistemas", href: "/sistemas" });
    });

    it("falls back to the catalogo breadcrumb for 'metrica' (from ActionsTable, D — SPEC only documents panel|catalogo)", () => {
      expect(resolveSistemaBreadcrumb("metrica")).toEqual({ label: "Sistemas", href: "/sistemas" });
    });

    it("falls back to the catalogo breadcrumb when ?from= is missing or unrecognized", () => {
      expect(resolveSistemaBreadcrumb(undefined)).toEqual({ label: "Sistemas", href: "/sistemas" });
      expect(resolveSistemaBreadcrumb("cualquier-otra-cosa")).toEqual({ label: "Sistemas", href: "/sistemas" });
    });
  });

  describe("A (panel) → D (metric detail): MetricCard carries no ?from=/?periodo= (by design, not a gap)", () => {
    it("links a metric card to /metricas/[slug] with no query string — Pantalla D never reads ?from= or ?periodo=", () => {
      render(<MetricCard metrica={metrica({ slug: "tasa-reactivacion", nombre: "Tasa de reactivación" })} />);

      const link = screen.getByRole("link") as HTMLAnchorElement;
      expect(link.getAttribute("href")).toBe("/metricas/tasa-reactivacion");
    });
  });

  describe("?periodo= stays on /panel across a period change (PeriodPicker)", () => {
    it("pushes the new value under PERIODO_SEARCH_PARAM on the current pathname", () => {
      render(
        <PeriodPicker
          options={[
            { value: "12m", label: "Últimos 12 meses" },
            { value: "6m", label: "Últimos 6 meses" },
          ]}
          value="12m"
        />,
      );

      fireEvent.change(screen.getByLabelText("Selector de período"), { target: { value: "6m" } });

      expect(pushMock).toHaveBeenCalledWith(`/panel?${PERIODO_SEARCH_PARAM}=6m`);
    });
  });

  describe("?agrupacion= toggle (MetricTypeFilter, Pantalla B) — same shareable-URL mechanism as ?periodo=", () => {
    it("pushes 'categoria' when the Categoría button is clicked from the embudo default", () => {
      render(<MetricTypeFilter value="embudo" />);

      fireEvent.click(screen.getByRole("button", { name: "Categoría" }));

      expect(pushMock).toHaveBeenCalledWith(`/panel?${AGRUPACION_SEARCH_PARAM}=categoria`);
    });

    it("does not push when clicking the already-active option", () => {
      pushMock.mockClear();
      render(<MetricTypeFilter value="embudo" />);

      fireEvent.click(screen.getByRole("button", { name: "Embudo" }));

      expect(pushMock).not.toHaveBeenCalled();
    });
  });
});
