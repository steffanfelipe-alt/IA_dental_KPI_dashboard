/**
 * lib/types/metricas.ts
 *
 * INVENTED SHAPE — NOT A BACKEND CONTRACT.
 *
 * `MetricaCalculada` mirrors the internal `resultado["kpis_calculados"][kpi_id]`
 * structure built by `parser/pipeline.py` (see lines ~493-497) and
 * `parser/cobertura_calidad/coverage.py:218-238`, but that structure is
 * NEVER returned by any current API endpoint. `GET /clinicas/{id}/diagnostico`
 * only returns the derived `Diagnostico[]` list (see `lib/types/api.ts`),
 * which carries a verdict (`estado`) and text-based `hechos`, not a raw
 * numeric value + period series.
 *
 * The Métricas grid on the veredicto page needs exactly that raw
 * value + series shape (design D "Métricas grid" requirement), so this
 * type is a documented, forward-looking invention: wiring it to real
 * data later will very likely require a backend change — either adding
 * `kpis_calculados` to `DiagnosticoResponse` or a new endpoint — not
 * just swapping a mock import for a `fetch` call. Do not treat this file
 * as a source of truth for what the backend actually sends today.
 */
export interface MetricaCalculada {
  kpi_id: number;
  nombre: string;
  valor: number;
  unidad: string;
  confianza: number;
  fuentes: string[];
  /** `{ "2026-01": 22.1, ... }` — null when the KPI has no meaningful time series. */
  serie: Record<string, number> | null;
  agregados: { promedio: number; mediana: number; ultimo: number } | null;
}
