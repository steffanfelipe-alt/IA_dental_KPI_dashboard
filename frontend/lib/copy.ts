import type { NivelEmbudo } from "@/lib/types";

/**
 * lib/copy.ts
 *
 * Central home for user-facing strings whose exact wording was confirmed
 * by Felipe rather than invented ad hoc inside a component. Grows per
 * phase as more screens ship — a string that already lives here should
 * be imported, not retyped, in the component that needs it.
 *
 * Block labels resolved 2026-08-12 (were open items in an earlier spec
 * revision, no longer placeholders): A1 = "Métricas principales"
 * (ordenadas por `impactoScore`), A2 = "Métricas críticas" (ordenadas
 * por `vulnerabilidadScore`). "Panel prioritario" names the whole
 * `/panel` screen, not a single block — see SPEC "Resolved 2026-08-12".
 *
 * `limiteAnclados` is EXACT copy from the tasks artifact (A3-bis, task
 * 4.3) — do not reword it, `SystemsBlock.test.tsx` asserts it verbatim.
 *
 * `sistemas.*` (PR5, Pantalla B): panorama/catálogo labels. Spanish
 * `nivelEmbudo` labels (`NIVEL_EMBUDO_LABEL`) and their funnel display
 * order (`NIVEL_EMBUDO_ORDEN`) were NOT in SPEC §10 (that section only
 * names the enum's raw values) — invented here as the natural
 * marketing-funnel reading order (captación → conversión → retención →
 * reactivación, con "operación" al final como categoría no-embudo),
 * a judgment call flagged in apply-progress, not SPEC-confirmed wording.
 *
 * `sistemas.metricasYEstado.*` (Slice 2 WU-B1 data layer, wired by WU-B2):
 * `tituloDirectas`/`tituloIndirectas` are the two section headers
 * `MetricasEstado.tsx` renders `MetricaConObjetivoSistema[]` under, split
 * by `relacion`. `disclaimerIndirectas` is the "possible improvement, no
 * promise" copy the spec's "Indirect metric labeled as non-promised"
 * scenario requires. `noImplementadoAun` is the SPEC "System not yet
 * implemented" scenario's explicit not-measurable state, shown instead of
 * a delta when a metric's `impactoReal` is `null`. WU-B2 deleted the
 * `bloqueMetricasYEstadoTodo` `TODO(felpa)` placeholder key WU-B1 kept
 * alive for exactly this handoff — `sistemas/page.tsx` now renders
 * `metricasYEstado.*` via `MetricasEstado` instead.
 */
export const COPY = {
  panel: {
    screenTitle: "Panel prioritario",
    bloqueMetricasPrincipales: "Métricas principales",
    bloqueMetricasCriticas: "Métricas críticas",
    bloqueSistemas: "Sistemas",
    bloqueSistemasAnclados: "Anclados por la clínica",
    bloqueSistemasCandidatos: "Otros sistemas que podés anclar",
    accionAnclar: "Anclar",
    accionDesanclar: "Desanclar",
    limiteAnclados: "Máximo 4 anclados. Desanclá uno para agregar otro.",
  },
  sistemas: {
    screenTitle: "Sistemas",
    panoramaTitulo: "Panorama",
    panoramaTotal: "Sistemas en el catálogo",
    bloqueCatalogo: "Catálogo",
    bloqueMetricasYEstado: "Métricas y estado",
    metricasYEstado: {
      tituloDirectas: "Métricas directas",
      tituloIndirectas: "Métricas indirectas",
      /** SPEC scenario "Indirect metric labeled as non-promised": possible improvement, never a promise. */
      disclaimerIndirectas: "Mejora posible gracias a este sistema, sin garantía: estas métricas no son su objetivo directo.",
      /** SPEC scenario "System not yet implemented": explicit not-measurable state instead of a delta. */
      noImplementadoAun: "Todavía no implementado: sin fecha de implementación, no hay impacto medible.",
    },
  },
} as const;

/** SPEC §10 raw enum values, Spanish display labels — see this file's header for the "not SPEC-confirmed wording" flag. */
export const NIVEL_EMBUDO_LABEL: Record<NivelEmbudo, string> = {
  captacion: "Captación",
  conversion: "Conversión",
  retencion: "Retención",
  reactivacion: "Reactivación",
  operacion: "Operación",
};

/** Funnel display order for grouping the catálogo by `nivelEmbudo` (SPEC "grouped by `nivelEmbudo` (default)"). */
export const NIVEL_EMBUDO_ORDEN: NivelEmbudo[] = ["captacion", "conversion", "retencion", "reactivacion", "operacion"];
