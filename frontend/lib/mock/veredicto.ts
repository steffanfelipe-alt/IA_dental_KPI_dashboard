/**
 * lib/mock/veredicto.ts
 *
 * Mock fixtures for the veredicto/diagnóstico page (design "mock-data-only").
 * `veredicto/page.tsx` imports these SERVER-side and passes them as props
 * to the client shell — no fetch, no network egress to `/diagnostico` or
 * `/informe` in this change (spec: "All content is mock-data-driven").
 *
 * - `MOCK_DIAGNOSTICO` and `MOCK_INFORME` follow the REAL backend response
 *   shapes 1:1 (`DiagnosticoResponse`/`InformeResponse` from `lib/types/api.ts`).
 * - `MOCK_METRICAS` follows the INVENTED `MetricaCalculada` shape
 *   (`lib/types/metricas.ts`) — see that file's docstring for why it isn't
 *   a real API contract yet.
 *
 * KPI universe (21 KPIs, ids 1-21) mirrors `parser/vocabulario/schema.py::KPI_FORMULAS`.
 */
import type { Diagnostico, DiagnosticoResponse, InformeResponse } from "../types/api";
import type { MetricaCalculada } from "../types/metricas";
import type { Direccion } from "../types";

const PERIODOS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"];

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

function serieDe(valores: number[]): Record<string, number> {
  const serie: Record<string, number> = {};
  PERIODOS.forEach((periodo, i) => {
    serie[periodo] = valores[i];
  });
  return serie;
}

/**
 * Transcribed 1:1 from `BENCHMARKS_AR[kpi_id].mejor_es`
 * (`parser/diagnostico/benchmarks.py`) — spec "Declared Metric Direction".
 * `null` for the 6 KPIs (11, 14, 16, 17, 18, 20) with no declared
 * direction there. NEVER inferred from the series trend.
 */
const DIRECCION_POR_KPI: Record<number, Direccion | null> = {
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

function agregadosDe(valores: number[]): { promedio: number; mediana: number; ultimo: number } {
  const ordenados = [...valores].sort((a, b) => a - b);
  const mid = Math.floor(ordenados.length / 2);
  const mediana =
    ordenados.length % 2 === 0 ? round1((ordenados[mid - 1] + ordenados[mid]) / 2) : round1(ordenados[mid]);
  return {
    promedio: round1(valores.reduce((a, b) => a + b, 0) / valores.length),
    mediana,
    ultimo: valores[valores.length - 1],
  };
}

function metricaConSerie(
  kpi_id: number,
  nombre: string,
  unidad: string,
  valores: number[],
  confianza: number,
  fuentes: string[],
): MetricaCalculada {
  return {
    kpi_id,
    nombre,
    valor: valores[valores.length - 1],
    unidad,
    confianza,
    fuentes,
    serie: serieDe(valores),
    agregados: agregadosDe(valores),
    direccion: DIRECCION_POR_KPI[kpi_id] ?? null,
  };
}

function metricaSinSerie(
  kpi_id: number,
  nombre: string,
  unidad: string,
  valor: number,
  confianza: number,
  fuentes: string[],
): MetricaCalculada {
  return {
    kpi_id,
    nombre,
    valor,
    unidad,
    confianza,
    fuentes,
    serie: null,
    agregados: null,
    direccion: DIRECCION_POR_KPI[kpi_id] ?? null,
  };
}

/**
 * ~21 KPIs (design "Métricas grid" requirement, matches the full KPI
 * universe in `parser/vocabulario/schema.py::KPI_FORMULAS`). Ids 17-20
 * carry `serie: null` because their real formulas don't produce a
 * meaningful monthly time series (deltas, per-treatment breakdowns, or
 * combined dict results) — kept as single-value metrics for the mock.
 */
export const MOCK_METRICAS: MetricaCalculada[] = [
  metricaConSerie(1, "Consultas nuevas / mes", "conteo", [42, 45, 41, 48, 50, 53], 0.92, ["planilla_turnos.xlsx"]),
  metricaConSerie(
    2,
    "Tiempo de 1ª respuesta",
    "min",
    [18.5, 17.2, 16.8, 15.5, 14.9, 14.2],
    0.85,
    ["planilla_mensajeria.xlsx"],
  ),
  metricaConSerie(
    3,
    "Tasa de agendamiento",
    "%",
    [62.0, 64.5, 63.0, 66.2, 68.0, 69.5],
    0.9,
    ["planilla_turnos.xlsx"],
  ),
  metricaConSerie(4, "Tasa de no-show", "%", [22.0, 21.4, 23.1, 20.8, 19.5, 18.9], 0.94, ["planilla_turnos.xlsx"]),
  metricaConSerie(
    5,
    "Tasa de aceptación de presupuestos",
    "%",
    [48.0, 50.2, 47.5, 52.1, 54.0, 55.8],
    0.88,
    ["planilla_presupuestos.xlsx"],
  ),
  metricaConSerie(
    6,
    "Ticket promedio",
    "$",
    [8200, 8450, 8100, 8700, 8950, 9200],
    0.91,
    ["planilla_presupuestos.xlsx"],
  ),
  metricaConSerie(
    7,
    "Tasa de finalización de tratamiento",
    "%",
    [71.0, 69.5, 73.2, 72.0, 74.5, 75.1],
    0.87,
    ["planilla_tratamientos.xlsx"],
  ),
  metricaConSerie(
    8,
    "Recall / retención",
    "%",
    [55.0, 56.2, 54.8, 57.5, 58.0, 59.3],
    0.83,
    ["planilla_pacientes.xlsx"],
  ),
  metricaConSerie(
    9,
    "Tasa de reactivación",
    "%",
    [12.0, 13.5, 11.8, 14.2, 15.0, 16.1],
    0.79,
    ["planilla_campanas.xlsx"],
  ),
  metricaConSerie(
    10,
    "Tasa de reseñas / referidos",
    "%",
    [8.5, 9.0, 8.2, 9.8, 10.1, 10.5],
    0.72,
    ["planilla_marketing.xlsx"],
  ),
  metricaConSerie(
    11,
    "Throughput (ingresos cobrados)",
    "$",
    [1250000, 1310000, 1180000, 1390000, 1420000, 1465000],
    0.95,
    ["planilla_facturacion.xlsx"],
  ),
  metricaConSerie(
    12,
    "Producción por hora-sillón",
    "$/hora",
    [3800, 3950, 3700, 4050, 4200, 4310],
    0.86,
    ["planilla_facturacion.xlsx", "planilla_agenda.xlsx"],
  ),
  metricaConSerie(
    13,
    "Tasa de cobro",
    "%",
    [88.0, 89.5, 87.2, 90.1, 91.0, 91.8],
    0.93,
    ["planilla_facturacion.xlsx"],
  ),
  metricaConSerie(
    14,
    "Valor del paciente (LTV)",
    "$",
    [42000, 43500, 41200, 44800, 45600, 46900],
    0.81,
    ["planilla_pacientes.xlsx"],
  ),
  metricaConSerie(
    15,
    "Horas/semana en tareas repetitivas",
    "hs/semana",
    [22.0, 21.0, 20.5, 19.0, 18.2, 17.5],
    0.7,
    ["respuestas_diagnostico"],
  ),
  metricaConSerie(
    16,
    "% de tareas repetitivas ya automatizadas",
    "%",
    [15.0, 18.5, 22.0, 26.5, 30.0, 34.2],
    0.68,
    ["respuestas_diagnostico"],
  ),
  metricaSinSerie(17, "Horas-persona liberadas / mes", "hs/mes", 68.5, 0.65, ["respuestas_diagnostico"]),
  metricaSinSerie(18, "Tareas que dependen de una sola persona", "conteo", 4, 0.75, ["respuestas_diagnostico"]),
  metricaSinSerie(
    19,
    "Costo adquisición vs. reactivación",
    "$/paciente",
    1850,
    0.6,
    ["planilla_marketing.xlsx", "planilla_campanas.xlsx"],
  ),
  metricaSinSerie(
    20,
    "Rentabilidad por tratamiento",
    "$",
    3200,
    0.58,
    ["planilla_tratamientos.xlsx", "planilla_costos.xlsx"],
  ),
  metricaConSerie(
    21,
    "Penetración de reactivación",
    "%",
    [9.0, 9.8, 9.2, 10.5, 11.0, 11.8],
    0.77,
    ["planilla_campanas.xlsx"],
  ),
];

const DIAGNOSTICOS: Diagnostico[] = [
  {
    kpi_id: 4,
    problema: "Tasa de no-show",
    estado: "PROBLEM",
    hechos: ["valor_actual=18.9", "direccion=por_encima_del_benchmark", "benchmark_alto=15.0"],
    anomalias: [
      { kpi_id: 4, estado: "PROBLEM", magnitud_pct: 26.0, confiabilidad_benchmark: "alta" },
    ],
    hipotesis: [
      {
        kpi_id: 4,
        causa_probable: "Falta de recordatorios automáticos antes del turno",
        confianza: "alta",
        preguntas_que_la_sustentan: ["¿Envían recordatorio de turno?", "¿Con cuánta anticipación confirman?"],
      },
    ],
    contradicciones: [],
    patrones_cruzados: [
      "La tasa de agendamiento sube pero el no-show también, sugiriendo que se agenda sin confirmar disponibilidad real del paciente.",
    ],
    informacion_faltante: ["Canal usado para confirmar turnos"],
    confianza: 0.86,
    prioridad: 1,
  },
  {
    kpi_id: 5,
    problema: "Tasa de aceptación de presupuestos",
    estado: "WATCH",
    hechos: ["valor_actual=55.8", "tendencia=creciente_ultimos_3_meses"],
    anomalias: [{ kpi_id: 5, estado: "WATCH", magnitud_pct: 8.5, confiabilidad_benchmark: "media" }],
    hipotesis: [
      {
        kpi_id: 5,
        causa_probable: "Presupuestos se presentan sin seguimiento posterior",
        confianza: "media",
        preguntas_que_la_sustentan: ["¿Hacen seguimiento a presupuestos no aceptados?"],
      },
    ],
    contradicciones: [],
    patrones_cruzados: [],
    informacion_faltante: [],
    confianza: 0.74,
    prioridad: 3,
  },
  {
    kpi_id: 6,
    problema: "Ticket promedio",
    estado: "HEALTHY",
    hechos: ["valor_actual=9200", "direccion=por_encima_del_benchmark"],
    anomalias: [],
    hipotesis: [],
    contradicciones: [],
    patrones_cruzados: ["El ticket promedio crece en línea con la producción por hora-sillón."],
    informacion_faltante: [],
    confianza: 0.91,
    prioridad: null,
  },
  {
    kpi_id: 8,
    problema: "Recall / retención",
    estado: "NORMAL",
    hechos: ["valor_actual=59.3", "direccion=dentro_del_rango_esperado"],
    anomalias: [],
    hipotesis: [],
    contradicciones: [],
    patrones_cruzados: [],
    informacion_faltante: ["Motivo de baja de pacientes que no vuelven a control"],
    confianza: 0.8,
    prioridad: null,
  },
  {
    kpi_id: 9,
    problema: "Tasa de reactivación",
    estado: "CRITICAL",
    hechos: ["valor_actual=16.1", "direccion=muy_por_debajo_del_benchmark", "benchmark_bajo=25.0"],
    anomalias: [
      { kpi_id: 9, estado: "CRITICAL", magnitud_pct: 35.6, confiabilidad_benchmark: "alta" },
    ],
    hipotesis: [
      {
        kpi_id: 9,
        causa_probable: "Sin campaña sistemática de reactivación de pacientes inactivos",
        confianza: "alta",
        preguntas_que_la_sustentan: [
          "¿Tienen un proceso de contacto a pacientes inactivos?",
          "¿Con qué frecuencia lo hacen?",
        ],
      },
    ],
    contradicciones: [
      {
        kpi_id: 9,
        descripcion:
          "El gasto en captación de pacientes nuevos es alto mientras la reactivación de pacientes existentes está casi abandonada.",
        preguntas_involucradas: ["¿Cuánto invierten en marketing de captación?", "¿Invierten en reactivación?"],
      },
    ],
    patrones_cruzados: [
      "Costo de adquisición vs. reactivación muestra que reactivar es más barato que captar, pero la clínica no lo aprovecha.",
    ],
    informacion_faltante: [],
    confianza: 0.9,
    prioridad: 1,
  },
  {
    kpi_id: 15,
    problema: "Horas/semana en tareas repetitivas",
    estado: "WATCH",
    hechos: ["valor_actual=17.5", "tendencia=decreciente"],
    anomalias: [],
    hipotesis: [
      {
        kpi_id: 15,
        causa_probable: "Tareas administrativas todavía se hacen a mano pese a bajar levemente",
        confianza: "media",
        preguntas_que_la_sustentan: ["¿Qué tareas manuales consumen más horas por semana?"],
      },
    ],
    contradicciones: [],
    patrones_cruzados: [],
    informacion_faltante: [],
    confianza: 0.68,
    prioridad: 4,
  },
  {
    kpi_id: 16,
    problema: "% de tareas repetitivas ya automatizadas",
    estado: "HEALTHY",
    hechos: ["valor_actual=34.2", "tendencia=creciente_sostenida"],
    anomalias: [],
    hipotesis: [],
    contradicciones: [],
    patrones_cruzados: [
      "El aumento de automatización coincide con la baja en horas/semana dedicadas a tareas repetitivas.",
    ],
    informacion_faltante: [],
    confianza: 0.72,
    prioridad: null,
  },
  {
    kpi_id: 19,
    problema: "Costo adquisición vs. reactivación",
    estado: "INSUFFICIENT_EVIDENCE",
    hechos: ["gasto_captacion_reportado=true", "gasto_reactivacion_reportado=false"],
    anomalias: [],
    hipotesis: [],
    contradicciones: [],
    patrones_cruzados: [],
    informacion_faltante: ["Gasto mensual en campañas de reactivación de pacientes inactivos"],
    confianza: 0.35,
    prioridad: 2,
  },
  {
    kpi_id: 3,
    problema: "Tasa de agendamiento",
    estado: "NORMAL",
    hechos: ["valor_actual=69.5", "direccion=dentro_del_rango_esperado"],
    anomalias: [],
    hipotesis: [],
    contradicciones: [],
    patrones_cruzados: [],
    informacion_faltante: [],
    confianza: 0.84,
    prioridad: null,
  },
  {
    kpi_id: 13,
    problema: "Tasa de cobro",
    estado: "HEALTHY",
    hechos: ["valor_actual=91.8", "direccion=por_encima_del_benchmark"],
    anomalias: [],
    hipotesis: [],
    contradicciones: [],
    patrones_cruzados: [],
    informacion_faltante: [],
    confianza: 0.93,
    prioridad: null,
  },
];

export const MOCK_DIAGNOSTICO: DiagnosticoResponse = { diagnostico: DIAGNOSTICOS };

// `texto` mirrors the real shape (one prose block, "informe jerárquico de
// 10 secciones" per `interpretar_clinica`'s docstring) so `InformeText`
// (Phase 4) has realistic headings + paragraphs to format, even though
// this Phase (1) does not render it.
export const MOCK_INFORME: InformeResponse = {
  texto: `# Resumen ejecutivo

La clínica muestra una base operativa sólida en facturación y cobro, con oportunidades claras en retención de pacientes y automatización de tareas administrativas. La tasa de no-show y la baja reactivación de pacientes inactivos son los dos puntos que más impacto tienen sobre el crecimiento sostenido.

## Fortalezas

El ticket promedio y la tasa de cobro están por encima del benchmark del sector, lo que indica una gestión financiera saludable. La producción por hora-sillón viene en aumento sostenido en los últimos seis meses, señal de que el tiempo clínico se está aprovechando mejor.

## Puntos débiles

La tasa de reactivación de pacientes inactivos es crítica: menos de la mitad del benchmark esperado, mientras el gasto en captación de pacientes nuevos se mantiene alto. Esto sugiere una oportunidad de bajo costo desaprovechada. La tasa de no-show también está por encima de lo saludable, probablemente por falta de un proceso sistemático de recordatorios y confirmación.

## Aceptación de presupuestos

La aceptación de presupuestos viene mejorando mes a mes, pero sigue por debajo de lo ideal. No hay evidencia de un proceso de seguimiento posterior a la presentación del presupuesto, lo que podría explicar parte de la brecha.

## Retención y recall

El recall de pacientes está dentro de un rango esperado, sin señales de alarma, aunque tampoco se destaca como fortaleza. Falta información sobre los motivos de baja de los pacientes que no vuelven a control.

## Automatización y carga operativa

Las horas semanales dedicadas a tareas repetitivas bajaron de forma sostenida, en línea con el aumento del porcentaje de tareas ya automatizadas. Esta tendencia, si se mantiene, debería seguir liberando tiempo del equipo administrativo.

## Costo de adquisición y reactivación

No hay información suficiente sobre el gasto en campañas de reactivación para comparar contra el costo de captación de pacientes nuevos. Esta es la brecha de información más importante detectada en este informe.

## Contradicciones detectadas

Se detectó una contradicción entre el alto gasto en captación de pacientes nuevos y la casi nula inversión en reactivación de pacientes existentes, pese a que reactivar suele ser más barato que captar.

## Próximos pasos sugeridos

Priorizar un proceso de recordatorio y confirmación de turnos para bajar el no-show, y lanzar una campaña sistemática de reactivación de pacientes inactivos aprovechando el menor costo relativo de esa acción.

## Cierre

En conjunto, la clínica tiene una base financiera sana sobre la cual construir; el mayor apalancamiento a corto plazo está en reducir la fuga de pacientes (no-show, reactivación) más que en captar pacientes nuevos.`,
};
