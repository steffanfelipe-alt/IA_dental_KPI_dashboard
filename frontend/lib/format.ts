/**
 * lib/format.ts
 *
 * SPEC §11.3: "Números con `Intl.NumberFormat('es-AR')`. Locale es-AR en
 * toda la app." One shared formatter for the common case (thousands
 * grouping, comma decimal separator) plus a currency convenience for
 * `unidad: 'ARS'` metrics — both built on the same locale, never a
 * hardcoded separator string in a component.
 */

const NUMERO_ES_AR = new Intl.NumberFormat("es-AR");

export function formatearNumero(valor: number, opciones?: Intl.NumberFormatOptions): string {
  if (!opciones) {
    return NUMERO_ES_AR.format(valor);
  }
  return new Intl.NumberFormat("es-AR", opciones).format(valor);
}

export function formatearMoneda(valor: number, moneda = "ARS"): string {
  return formatearNumero(valor, { style: "currency", currency: moneda, maximumFractionDigits: 0 });
}
