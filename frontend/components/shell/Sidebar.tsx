"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { NAV_ITEMS } from "@/lib/nav";
import { useSidebar } from "./AppShell";

/**
 * Small inline-SVG nav icons keyed by href. `Sistema.icono` (SPEC §10)
 * names a Lucide icon for the systems catalog (Phase 7/PR5) — that's a
 * separate, later icon-by-name lookup for a different data source. These
 * two are just the fixed sidebar entries, so a tiny local set avoids
 * pulling in an icon library a whole PR early for two static icons.
 */
const NAV_ICONS: Record<string, ReactNode> = {
  "/panel": (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-5 w-5" aria-hidden="true">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  ),
  "/sistemas": (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-5 w-5" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <circle cx="5" cy="5" r="2" />
      <circle cx="19" cy="5" r="2" />
      <circle cx="5" cy="19" r="2" />
      <circle cx="19" cy="19" r="2" />
      <path d="M6.4 6.4 9.8 9.8M17.6 6.4 14.2 9.8M6.4 17.6 9.8 14.2M17.6 17.6 14.2 14.2" />
    </svg>
  ),
};

const COLLAPSE_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-4 w-4" aria-hidden="true">
    <path d="M15 6 9 12l6 6" />
  </svg>
);

const EXPAND_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-4 w-4" aria-hidden="true">
    <path d="M9 6l6 6-6 6" />
  </svg>
);

/**
 * components/shell/Sidebar.tsx
 *
 * SPEC §3: expanded 240px / collapsed 64px (icon-only), 180ms transition,
 * state in `AppShell`'s React context (no localStorage). `w-60` = 15rem =
 * 240px, `w-16` = 4rem = 64px — exact px targets via plain Tailwind scale,
 * no arbitrary width values needed.
 */
export function Sidebar() {
  const pathname = usePathname();
  const { collapsed, toggleCollapsed } = useSidebar();

  return (
    <aside
      className={`flex shrink-0 flex-col border-r border-border-subtle bg-surface transition-[width] duration-[180ms] ease-in-out ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      <div className="flex items-center justify-between px-4 py-4">
        {!collapsed && <span className="truncate text-sm font-semibold text-text-strong">Agencia IA Dental</span>}
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Expandir menú" : "Colapsar menú"}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-canvas focus:outline-none focus:ring-2 focus:ring-primary-100"
        >
          {collapsed ? EXPAND_ICON : COLLAPSE_ICON}
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-2 py-2" aria-label="Navegación principal">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary-100 ${
                active ? "bg-primary-50 text-primary-700" : "text-text-body hover:bg-canvas"
              }`}
            >
              <span className="shrink-0">{NAV_ICONS[item.href]}</span>
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
