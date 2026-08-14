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

// Exported so `lib/data/panel.ts::getPanel` can use it as the reference
// for "how many real periods are actually available" when windowing
// `valorActual`/`valorAnterior` by `?periodo=` (Phase 4/U5) — it must not
// hardcode `24` separately from this fixture's own period count.
export const PERIODOS_24M = generarPeriodos(CANTIDAD_MESES, ANIO_FIN, MES_FIN);

function siguientePeriodo(periodo: string): string {
  const [anioStr, mesStr] = periodo.split("-");
  let anio = Number(anioStr);
  let mes = Number(mesStr) + 1;
  if (mes > 12) {
    mes = 1;
    anio += 1;
  }
  return `${anio}-${String(mes).padStart(2, "0")}`;
}

/**
 * Deterministic trend + light noise, never `Math.random()` (stable
 * fixtures). `mesesProyectados` (Pantalla D, task 5.1/5.4) appends
 * forward-looking points past the last real period, continuing the same
 * `valorInicial→valorFinal` slope and marked `proyectado: true` — SPEC
 * "Real vs projected data separation": `MetricChart` MUST render these
 * as a distinct dashed segment, never merged with real data. This is a
 * general "si la tendencia continúa" forecast, independent of any one
 * system's proposed impact (see `lib/data/metricas.ts`'s
 * `calcularImpactoEstimadoPct`, a different, action-specific number).
 */
function generarSerie(
  valorInicial: number,
  valorFinal: number,
  decimales = 1,
  amplitudRuido = 0,
  mesesProyectados = 0,
): PuntoSerie[] {
  const factor = 10 ** decimales;
  const serieReal: PuntoSerie[] = PERIODOS_24M.map((periodo, indice) => {
    const progreso = indice / (PERIODOS_24M.length - 1);
    const base = valorInicial + (valorFinal - valorInicial) * progreso;
    const ruido = amplitudRuido ? Math.sin(indice * 1.3) * amplitudRuido : 0;
    const valor = Math.round((base + ruido) * factor) / factor;
    return { periodo, valor, proyectado: false };
  });

  if (mesesProyectados <= 0) {
    return serieReal;
  }

  const pendientePorMes = (valorFinal - valorInicial) / (PERIODOS_24M.length - 1);
  const puntosProyectados: PuntoSerie[] = [];
  let periodoActual = serieReal[serieReal.length - 1].periodo;
  for (let i = 1; i <= mesesProyectados; i++) {
    periodoActual = siguientePeriodo(periodoActual);
    const valor = Math.round((valorFinal + pendientePorMes * i) * factor) / factor;
    puntosProyectados.push({ periodo: periodoActual, valor, proyectado: true });
  }

  return [...serieReal, ...puntosProyectados];
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
  /** Forward-looking `proyectado: true` points appended past the last real period (Pantalla D). */
  mesesProyectados?: number;
  impactoScore: number;
  vulnerabilidadScore: number;
  sistemasAsociados: SistemaRef[];
}

function metrica(fixture: MetricaFixture): Metrica {
  const serie = generarSerie(
    fixture.valorInicial,
    fixture.valorFinal,
    fixture.decimales ?? 1,
    fixture.amplitudRuido ?? 0,
    fixture.mesesProyectados ?? 0,
  );
  // `valorActual`/`valorAnterior` MUST always reflect the last two REAL
  // periods, never a projected one, even when `mesesProyectados` extends
  // `serie` past them — Pantalla A's `MetricCard`/`TrendValue` and
  // `semantics.ts::evaluarMetrica` all assume "current value", not "our
  // own forecast", and PR2 already shipped/tested against that.
  const puntosReales = serie.filter((punto) => !punto.proyectado);
  const valorActual = puntosReales[puntosReales.length - 1].valor;
  const valorAnterior = puntosReales[puntosReales.length - 2].valor;
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
    // kpi_id 4 ("Tasa de no-show", KPI_FORMULAS) — BENCHMARKS_AR[4] is
    // confiabilidad: "consultora_ar", rango_bajo=8/rango_alto=15. 12 sits
    // inside that real range (a healthy target, not the excellent floor).
    objetivo: 12,
    valorInicial: 26,
    valorFinal: 18.9,
    amplitudRuido: 0.6,
    mesesProyectados: 3,
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
    // kpi_id 9 ("Tasa de reactivación", KPI_FORMULAS) — BENCHMARKS_AR[9] is
    // confiabilidad: "proxy_internacional", rango_bajo=15/rango_alto=25.
    // 25 is the top of that real range.
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
    // kpi_id 5 ("Tasa de aceptación de presupuestos", KPI_FORMULAS) —
    // BENCHMARKS_AR[5] is confiabilidad: "proxy_internacional",
    // rango_bajo=65/rango_alto=75. 65 is the floor of that real range.
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
    // kpi_id 1 ("Consultas nuevas / mes", KPI_FORMULAS) — BENCHMARKS_AR[1]
    // is confiabilidad: "sin_benchmark" (raw count, no universal target
    // possible — it depends 100% on clinic size). No numeric objetivo may
    // be fabricated here.
    objetivo: null,
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
    // kpi_id 12 ("Producción por hora-sillón", KPI_FORMULAS) —
    // BENCHMARKS_AR[12] is confiabilidad: "proxy_internacional" but
    // rango_bajo/rango_alto are both None (USD proxy, no ARS exchange-rate
    // figure the backend trusts — see benchmarks.py module docstring). No
    // rango means no real number to transcribe.
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
    // kpi_id 15 ("Horas/semana en tareas repetitivas", KPI_FORMULAS) —
    // BENCHMARKS_AR[15] is confiabilidad: "proxy_internacional" but
    // rango_bajo/rango_alto are both None (regional estimate, not an
    // auditable hard figure — see benchmarks.py module docstring). No
    // rango means no real number to transcribe, so objetivo stays null
    // even though confiabilidad isn't literally "sin_benchmark".
    objetivo: null,
    valorInicial: 24,
    valorFinal: 17.5,
    amplitudRuido: 0.4,
    impactoScore: 58,
    vulnerabilidadScore: 62,
    sistemasAsociados: [{ slug: "automatizacion-cobros", nombre: "Automatización de cobros", estado: "disponible" }],
  }),
];
