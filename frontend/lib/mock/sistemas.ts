/**
 * lib/mock/sistemas.ts
 *
 * System fixtures for Pantalla A/B/C (`/panel`, `/sistemas`,
 * `/sistemas/[slug]` — PR2/PR4/PR6) — `lib/types.ts::Sistema`, populated
 * as-is (no reshaping). Imports `MOCK_METRICAS` from `lib/mock/panel.ts`
 * one-way (this file depends on that one, never the reverse — see that
 * file's header) to build each system's `metricas` field without
 * duplicating series-generation logic.
 *
 * Seven systems — covering every `EstadoSistema` (implementado x2,
 * en_proceso, sugerido, disponible x3) and all five `NivelEmbudo` values
 * at least once: two manually anchored `disponible` systems (SPEC §5
 * A3-bis, max 4) so the anchoring UI (PR2) has a non-empty, non-maxed
 * starting fixture, plus one NOT-yet-anchored `disponible` system so
 * PR2's "Otros sistemas que podés anclar" candidate list (see
 * `components/systems/SystemsBlock.tsx`) has something real to render
 * against in a manual `/panel` check. PR4/PR6 extend this list if a
 * screen needs more variety once it's actually being built against.
 *
 * Slice 2 (WU-B1, "Métricas y estado"): every `metricaAsociada` call now
 * tags `relacion` — "directa" (the system's `kpi_objetivo`) or
 * "indirecta" (possible improvement, no promise — `kpis_secundarios`).
 * `recordatorios-turnos` (already `implementado`) gets 9 indirect
 * associations on top of its existing direct one, so the "Métricas y
 * estado" block (WU-B2) has a real "exhaustive indirect listing, no
 * show-more" fixture (SPEC scenario) to render against — the 4 new
 * `lib/mock/panel.ts` metrics exist for exactly this.
 */
import type { CredencialSistema, DependenciaSistema, MetricaConObjetivoSistema, PasoSistema, Sistema } from "@/lib/types";
import { MOCK_METRICAS } from "@/lib/mock/panel";

function metricaAsociada(
  slug: string,
  objetivoPostSistema: number | null,
  valorAlImplementar: number | null,
  relacion: NonNullable<MetricaConObjetivoSistema["relacion"]>,
): MetricaConObjetivoSistema {
  const base = MOCK_METRICAS.find((m) => m.slug === slug);
  if (!base) {
    throw new Error(`lib/mock/sistemas.ts: no existe la métrica mockeada "${slug}" en lib/mock/panel.ts`);
  }
  return { ...base, objetivoPostSistema, valorAlImplementar, relacion };
}

function paso(id: string, titulo: string, responsable: PasoSistema["responsable"], completado: boolean): PasoSistema {
  return { id, titulo, completado, responsable };
}

export const MOCK_SISTEMAS: Sistema[] = [
  {
    slug: "recordatorios-turnos",
    nombre: "Recordatorios automáticos de turnos",
    descripcionCorta: "WhatsApp + SMS automático 48h y 2h antes de cada turno, con confirmación de un toque.",
    icono: "bell-ring",
    nivelEmbudo: "retencion",
    categoria: "Comunicación",
    estado: "implementado",
    progresoPct: 100,
    sugeridoPorVeredicto: false,
    anclado: false,
    fechaImplementacion: "2025-11-02",
    pasos: [
      paso("recordatorios-1", "Conectar número de WhatsApp Business", "clinica", true),
      paso("recordatorios-2", "Activar envío automático 48h/2h antes", "automatico", true),
    ],
    dependencias: [],
    credenciales: [{ id: "recordatorios-cred-1", nombre: "Token de WhatsApp Business API", estado: "verificada", instrucciones: "Ya verificado, no requiere acción." } satisfies CredencialSistema],
    metricas: [
      metricaAsociada("tasa-no-show", 10, 26, "directa"),
      // 9 indirect associations (SPEC "Exhaustive indirect listing"):
      // possible improvement from fewer no-shows / better communication,
      // never this system's promised target.
      metricaAsociada("tiempo-primera-respuesta", null, 6.5, "indirecta"),
      metricaAsociada("tasa-agendamiento", null, 30, "indirecta"),
      metricaAsociada("tasa-recall-retencion", null, 58, "indirecta"),
      metricaAsociada("tasa-cobro", null, 87, "indirecta"),
      metricaAsociada("tasa-reactivacion", null, 10, "indirecta"),
      metricaAsociada("tasa-aceptacion-presupuestos", null, 47, "indirecta"),
      metricaAsociada("consultas-nuevas", null, 40, "indirecta"),
      metricaAsociada("produccion-hora-sillon", null, 3600, "indirecta"),
      metricaAsociada("horas-tareas-repetitivas", null, 24, "indirecta"),
    ],
  },
  {
    slug: "campana-reactivacion",
    nombre: "Campaña de reactivación de pacientes inactivos",
    descripcionCorta: "Secuencia automática de contacto a pacientes sin visitas en más de 6 meses.",
    icono: "refresh-ccw",
    nivelEmbudo: "reactivacion",
    categoria: "Marketing",
    estado: "en_proceso",
    progresoPct: 45,
    sugeridoPorVeredicto: true,
    motivoSugerencia:
      "La tasa de reactivación está muy por debajo del benchmark mientras el gasto en captación de pacientes nuevos se mantiene alto: reactivar sale más barato que captar.",
    anclado: false,
    pasos: [
      paso("reactivacion-1", "Cargar base de pacientes inactivos", "clinica", true),
      paso("reactivacion-2", "Aprobar guion de mensajes de la campaña", "clinica", false),
      paso("reactivacion-3", "Activar envío automático mensual", "automatico", false),
    ],
    dependencias: [{ id: "reactivacion-dep-1", titulo: "Recordatorios de turnos activo", requerida: false, cumplida: true, sistemaSlug: "recordatorios-turnos" } satisfies DependenciaSistema],
    credenciales: [{ id: "reactivacion-cred-1", nombre: "Token de WhatsApp Business API", estado: "pendiente", instrucciones: "Compartir el token generado en Meta Business Suite." } satisfies CredencialSistema],
    metricas: [metricaAsociada("tasa-reactivacion", 22, null, "directa")],
  },
  {
    slug: "seguimiento-presupuestos",
    nombre: "Seguimiento automático de presupuestos",
    descripcionCorta: "Recordatorios escalonados a pacientes con presupuesto presentado y sin respuesta.",
    icono: "file-clock",
    nivelEmbudo: "conversion",
    categoria: "Ventas",
    estado: "sugerido",
    progresoPct: 0,
    sugeridoPorVeredicto: true,
    motivoSugerencia:
      "La tasa de aceptación de presupuestos viene mejorando pero sigue lejos del objetivo: automatizar el seguimiento evita que las propuestas se enfríen sin respuesta.",
    anclado: false,
    pasos: [paso("presupuestos-1", "Conectar planilla de presupuestos", "clinica", false)],
    dependencias: [],
    credenciales: [],
    metricas: [metricaAsociada("tasa-aceptacion-presupuestos", 65, null, "directa")],
  },
  {
    slug: "programa-referidos",
    nombre: "Programa de referidos",
    descripcionCorta: "Incentivo automático a pacientes que refieren a un paciente nuevo.",
    icono: "gift",
    nivelEmbudo: "captacion",
    categoria: "Marketing",
    estado: "disponible",
    progresoPct: 0,
    sugeridoPorVeredicto: false,
    anclado: true,
    pasos: [paso("referidos-1", "Definir el incentivo a ofrecer", "clinica", false)],
    dependencias: [],
    credenciales: [],
    metricas: [metricaAsociada("consultas-nuevas", 70, null, "directa")],
  },
  {
    slug: "dashboard-financiero",
    nombre: "Dashboard financiero en tiempo real",
    descripcionCorta: "Producción, cobranza y ocupación de sillón consolidados en un solo tablero.",
    icono: "line-chart",
    nivelEmbudo: "operacion",
    categoria: "Finanzas",
    estado: "implementado",
    progresoPct: 100,
    sugeridoPorVeredicto: false,
    anclado: false,
    fechaImplementacion: "2025-06-15",
    pasos: [paso("financiero-1", "Conectar planilla de facturación", "clinica", true)],
    dependencias: [],
    credenciales: [],
    metricas: [metricaAsociada("produccion-hora-sillon", null, 3600, "directa")],
  },
  {
    slug: "automatizacion-cobros",
    nombre: "Automatización de cobros",
    descripcionCorta: "Concilia pagos y emite recordatorios de cobro pendiente sin intervención manual.",
    icono: "credit-card",
    nivelEmbudo: "operacion",
    categoria: "Finanzas",
    estado: "disponible",
    progresoPct: 0,
    sugeridoPorVeredicto: false,
    anclado: true,
    pasos: [paso("cobros-1", "Conectar pasarela de pagos", "clinica", false)],
    dependencias: [],
    credenciales: [],
    metricas: [metricaAsociada("horas-tareas-repetitivas", 8, null, "directa")],
  },
  {
    slug: "encuestas-post-turno",
    nombre: "Encuestas post-turno",
    descripcionCorta: "Encuesta corta automática después de cada turno para medir satisfacción.",
    icono: "clipboard-list",
    nivelEmbudo: "retencion",
    categoria: "Comunicación",
    estado: "disponible",
    progresoPct: 0,
    sugeridoPorVeredicto: false,
    anclado: false,
    pasos: [paso("encuestas-1", "Elegir plataforma de encuestas", "clinica", false)],
    dependencias: [],
    credenciales: [],
    metricas: [metricaAsociada("tasa-no-show", 10, 26, "directa")],
  },
];
