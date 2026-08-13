/**
 * lib/mock/panel.ts
 *
 * Metric fixtures for Pantalla A (`/panel`, PR2) and Pantalla D
 * (`/metricas/[slug]`, PR3) — `lib/types.ts::Metrica`, populated as-is
 * (no reshaping). 24-month synthetic series (SPEC §12 "usar los datos
 * sintéticos de 24 meses"), ending the month before this change
 * (`2026-07`), generated deterministically so re-running never produces
 * different fixture values.
 *
 * Six metrics — enough to cover both `direccion` values, an `objetivo:
 * null` case, and the "high impact AND high vulnerability" overlap
 * scenario (SPEC "metric in both blocks") without padding the fixture
 * with near-duplicate entries; PR2/PR3 extend this list if a screen
 * needs more variety once it's actually being built against.
 *
 * `sistemasAsociados` embeds `SistemaRef` literals (slug/nombre/estado)
 * matching `lib/mock/sistemas.ts` — this file does NOT import that one
 * (kept import-direction one-way: `sistemas.ts` imports from here, not
 * the other way, see that file's header), so those slugs/nombres/estados
 * must stay in sync by hand, same as a real API would denormalize a
 * foreign reference into an embedded object.
 */
import type { Metrica, PuntoSerie, SistemaRef } from "@/lib/types";

const CANTIDAD_MESES = 24;
const ANIO_FIN = 2026;
const MES_FIN = 7; // último mes cerrado antes de este cambio (hoy: 2026-08)

function generarPeriodos(cantidad: number, anioFin: number, mesFin: number): string[] {
  const periodos: string[] = [];
  for (let i = cantidad - 1; i >= 0; i--) {
    let mes = mesFin - i;
    let anio = anioFin;
    while (mes <= 0) {
      mes += 12;
      anio -= 1;
    }
    periodos.push(`${anio}-${String(mes).padStart(2, "0")}`);
  }
  return periodos;
}

const PERIODOS_24M = generarPeriodos(CANTIDAD_MESES, ANIO_FIN, MES_FIN);

/** Deterministic trend + light noise, never `Math.random()` (stable fixtures). */
function generarSerie(valorInicial: number, valorFinal: number, decimales = 1, amplitudRuido = 0): PuntoSerie[] {
  const factor = 10 ** decimales;
  return PERIODOS_24M.map((periodo, indice) => {
    const progreso = indice / (PERIODOS_24M.length - 1);
    const base = valorInicial + (valorFinal - valorInicial) * progreso;
    const ruido = amplitudRuido ? Math.sin(indice * 1.3) * amplitudRuido : 0;
    const valor = Math.round((base + ruido) * factor) / factor;
    return { periodo, valor, proyectado: false };
  });
}

interface MetricaFixture {
  slug: string;
  nombre: string;
  unidad: string;
  definicion: string;
  porQueImporta: string;
  tipo: string;
  direccion: Metrica["direccion"];
  objetivo: number | null;
  valorInicial: number;
  valorFinal: number;
  decimales?: number;
  amplitudRuido?: number;
  impactoScore: number;
  vulnerabilidadScore: number;
  sistemasAsociados: SistemaRef[];
}

function metrica(fixture: MetricaFixture): Metrica {
  const serie = generarSerie(fixture.valorInicial, fixture.valorFinal, fixture.decimales ?? 1, fixture.amplitudRuido ?? 0);
  const valorActual = serie[serie.length - 1].valor;
  const valorAnterior = serie[serie.length - 2].valor;
  return {
    slug: fixture.slug,
    nombre: fixture.nombre,
    unidad: fixture.unidad,
    definicion: fixture.definicion,
    porQueImporta: fixture.porQueImporta,
    tipo: fixture.tipo,
    direccion: fixture.direccion,
    valorActual,
    valorAnterior,
    objetivo: fixture.objetivo,
    serie,
    impactoScore: fixture.impactoScore,
    vulnerabilidadScore: fixture.vulnerabilidadScore,
    sistemasAsociados: fixture.sistemasAsociados,
  };
}

export const MOCK_METRICAS: Metrica[] = [
  metrica({
    slug: "tasa-no-show",
    nombre: "Tasa de no-show",
    unidad: "%",
    definicion: "Turnos agendados que el paciente no honró, sobre el total de turnos del período.",
    porQueImporta: "Cada no-show es una silla vacía que ya tenía costo fijo asignado.",
    tipo: "retencion",
    direccion: "menor_mejor",
    objetivo: 12,
    valorInicial: 26,
    valorFinal: 18.9,
    amplitudRuido: 0.6,
    impactoScore: 92,
    vulnerabilidadScore: 88,
    sistemasAsociados: [{ slug: "recordatorios-turnos", nombre: "Recordatorios automáticos de turnos", estado: "implementado" }],
  }),
  metrica({
    slug: "tasa-reactivacion",
    nombre: "Tasa de reactivación",
    unidad: "%",
    definicion: "Pacientes inactivos (+6 meses sin visita) que volvieron a agendar en el período.",
    porQueImporta: "Reactivar un paciente existente cuesta una fracción de captar uno nuevo.",
    tipo: "reactivacion",
    direccion: "mayor_mejor",
    objetivo: 25,
    valorInicial: 10,
    valorFinal: 16.1,
    amplitudRuido: 0.4,
    impactoScore: 78,
    vulnerabilidadScore: 95,
    sistemasAsociados: [{ slug: "campana-reactivacion", nombre: "Campaña de reactivación de pacientes inactivos", estado: "en_proceso" }],
  }),
  metrica({
    slug: "tasa-aceptacion-presupuestos",
    nombre: "Tasa de aceptación de presupuestos",
    unidad: "%",
    definicion: "Presupuestos presentados que el paciente aceptó, sobre el total presentado.",
    porQueImporta: "Un presupuesto no aceptado es tratamiento identificado que no se convierte en ingreso.",
    tipo: "conversion",
    direccion: "mayor_mejor",
    objetivo: 65,
    valorInicial: 47,
    valorFinal: 55.8,
    amplitudRuido: 0.5,
    impactoScore: 70,
    vulnerabilidadScore: 55,
    sistemasAsociados: [{ slug: "seguimiento-presupuestos", nombre: "Seguimiento automático de presupuestos", estado: "sugerido" }],
  }),
  metrica({
    slug: "consultas-nuevas",
    nombre: "Consultas nuevas por mes",
    unidad: "turnos",
    definicion: "Pacientes nuevos que agendaron su primera consulta en el período.",
    porQueImporta: "Es el tope del embudo: sin captación nueva, todo lo demás corre sobre una base fija.",
    tipo: "captacion",
    direccion: "mayor_mejor",
    objetivo: 70,
    valorInicial: 40,
    valorFinal: 53,
    decimales: 0,
    amplitudRuido: 1.5,
    impactoScore: 85,
    vulnerabilidadScore: 40,
    sistemasAsociados: [{ slug: "programa-referidos", nombre: "Programa de referidos", estado: "disponible" }],
  }),
  metrica({
    slug: "produccion-hora-sillon",
    nombre: "Producción por hora-sillón",
    unidad: "ARS",
    definicion: "Facturación generada por hora de sillón ocupada.",
    porQueImporta: "Mide qué tan bien se aprovecha el tiempo clínico disponible, no solo cuánto se cobra.",
    tipo: "operacion",
    direccion: "mayor_mejor",
    objetivo: null,
    valorInicial: 3600,
    valorFinal: 4310,
    decimales: 0,
    amplitudRuido: 40,
    impactoScore: 66,
    vulnerabilidadScore: 20,
    sistemasAsociados: [{ slug: "dashboard-financiero", nombre: "Dashboard financiero en tiempo real", estado: "implementado" }],
  }),
  metrica({
    slug: "horas-tareas-repetitivas",
    nombre: "Horas/semana en tareas repetitivas",
    unidad: "hs/semana",
    definicion: "Horas-persona por semana dedicadas a tareas administrativas manuales y repetibles.",
    porQueImporta: "Cada hora en tareas repetitivas es una hora que no se dedica a pacientes o a mejorar el negocio.",
    tipo: "operacion",
    direccion: "menor_mejor",
    objetivo: 8,
    valorInicial: 24,
    valorFinal: 17.5,
    amplitudRuido: 0.4,
    impactoScore: 58,
    vulnerabilidadScore: 62,
    sistemasAsociados: [{ slug: "automatizacion-cobros", nombre: "Automatización de cobros", estado: "disponible" }],
  }),
];
