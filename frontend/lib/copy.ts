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
  },
} as const;
