/**
 * lib/types.ts
 *
 * SPEC §10 "Contratos de datos (TypeScript)" — transcribed verbatim.
 * These are the real Slice 1 contracts: `lib/mock/*` populates them
 * as-is (design "no reshaping"), and the future BFF response bodies
 * (Slice 2) must satisfy these shapes unchanged for `lib/data/*` loader
 * callers to keep working with zero component churn.
 *
 * `CredencialSistema` deliberately has no `valor` field — SPEC §10's
 * comment on that type ("NUNCA existe un campo `valor`...") is a
 * security invariant, not a style note: a raw credential value must
 * never round-trip through this frontend contract, on purpose.
 */

export type Direccion = "mayor_mejor" | "menor_mejor";

export type NivelEmbudo = "captacion" | "conversion" | "retencion" | "reactivacion" | "operacion";

export type EstadoSistema = "implementado" | "en_proceso" | "sugerido" | "disponible";

export interface PuntoSerie {
  periodo: string; // ISO date o 'YYYY-MM'
  valor: number;
  proyectado: boolean; // true → se dibuja punteado
}

export interface Metrica {
  slug: string;
  nombre: string;
  unidad: string; // '%', 'turnos', 'ARS', ...
  definicion: string; // "cómo se calcula"
  porQueImporta: string; // fundamento del objetivo
  tipo: string; // para el filtro de chips
  direccion: Direccion; // CRÍTICO: define qué es "mejorar"
  valorActual: number;
  valorAnterior: number;
  objetivo: number | null;
  serie: PuntoSerie[];
  impactoScore: number; // orden del bloque A1 — lo calcula el backend
  vulnerabilidadScore: number; // orden del bloque A2 — lo calcula el backend
  sistemasAsociados: SistemaRef[];
}

export interface SistemaRef {
  slug: string;
  nombre: string;
  estado: EstadoSistema;
}

export interface AccionSobreMetrica {
  sistema: SistemaRef;
  impactoEstimadoPct: number;
  valorProyectado: number;
  porQueServiria: string; // el "por qué serviría / es posible" de la nota
}

export interface PasoSistema {
  id: string;
  titulo: string;
  descripcion?: string;
  completado: boolean;
  responsable: "clinica" | "agencia" | "automatico";
}

export interface DependenciaSistema {
  id: string;
  titulo: string;
  requerida: boolean;
  cumplida: boolean;
  sistemaSlug?: string; // si la dependencia es otro sistema
}

export interface CredencialSistema {
  id: string;
  nombre: string;
  estado: "pendiente" | "recibida" | "verificada";
  instrucciones: string; // markdown corto
  // NUNCA existe un campo `valor` en el tipo del frontend. A propósito.
}

export interface Sistema {
  slug: string;
  nombre: string;
  descripcionCorta: string;
  icono: string; // nombre del ícono de Lucide
  nivelEmbudo: NivelEmbudo;
  categoria: string;
  estado: EstadoSistema;
  progresoPct: number; // 0-100
  sugeridoPorVeredicto: boolean;
  motivoSugerencia?: string;
  anclado: boolean; // anclaje manual al panel (máx. 4 por clínica)
  pasos: PasoSistema[];
  dependencias: DependenciaSistema[];
  credenciales: CredencialSistema[];
  metricas: MetricaConObjetivoSistema[];
  fechaImplementacion?: string;
}

export interface MetricaConObjetivoSistema extends Metrica {
  objetivoPostSistema: number | null;
  valorAlImplementar: number | null; // para medir el delta real
  /**
   * Slice 2 "Métricas y estado" (`/sistemas`): "directa" = vinculada por
   * `kpi_objetivo` (el sistema promete moverla), "indirecta" = vinculada
   * por `kpis_secundarios` (mejora posible, sin promesa). Optional porque
   * Slice 1 fixtures/consumers (`MetricCard`, `lib/data/metricas.ts`)
   * predate this split and never set it.
   */
  relacion?: "directa" | "indirecta";
  /**
   * Delta real desde `Sistema.fechaImplementacion`: `signo(direccion) *
   * (valorActual - valorAlImplementar)`. `null` cuando el sistema todavía
   * no tiene `fechaImplementacion` (nada que medir todavía) — ver
   * `lib/data/sistemas.ts::getSistema`. Optional for the same Slice 1
   * back-compat reason as `relacion`.
   */
  impactoReal?: number | null;
}
