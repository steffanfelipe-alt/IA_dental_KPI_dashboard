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
