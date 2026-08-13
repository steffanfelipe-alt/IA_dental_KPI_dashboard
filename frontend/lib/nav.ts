/**
 * lib/nav.ts
 *
 * Single source of truth for the sidebar's nav entries (SPEC §3: "Dejá
 * el array de nav en un solo archivo porque van a entrar más secciones").
 * `Sidebar` renders this array — new sections append here, not inline in
 * the component.
 */
export interface NavItem {
  label: string;
  href: string;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Panel prioritario", href: "/panel" },
  { label: "Sistemas", href: "/sistemas" },
];

/**
 * `?from=` breadcrumb resolution for Pantalla C (`/sistemas/[slug]`,
 * SPEC "Pantalla C — System Detail": "differing only by
 * `?from=panel|catalogo`"). Extracted here (PR5) from what was inline
 * `BREADCRUMB`/`BREADCRUMB_DEFAULT` constants in
 * `app/(app)/(dashboard)/sistemas/[slug]/page.tsx` (PR4) so the mapping
 * is a plain, testable function instead of only reachable by rendering
 * the full async server page (which needs a request-scoped `cookies()`
 * call this module has no dependency on) — this PR's integration tests
 * (task 7.5) exercise it directly. Behavior is unchanged: `?from=metrica`
 * (the undocumented third value `ActionsTable`, PR3, emits — see that
 * page's header comment) and any unrecognized/missing value still fall
 * back to the `catalogo` target, same as before this refactor.
 */
export interface SistemaBreadcrumb {
  label: string;
  href: string;
}

const SISTEMA_BREADCRUMB_BY_FROM: Record<string, SistemaBreadcrumb> = {
  panel: { label: "Panel prioritario", href: "/panel" },
  catalogo: { label: "Sistemas", href: "/sistemas" },
};

const SISTEMA_BREADCRUMB_DEFAULT: SistemaBreadcrumb = SISTEMA_BREADCRUMB_BY_FROM.catalogo;

export function resolveSistemaBreadcrumb(from: string | undefined): SistemaBreadcrumb {
  return (from && SISTEMA_BREADCRUMB_BY_FROM[from]) || SISTEMA_BREADCRUMB_DEFAULT;
}
