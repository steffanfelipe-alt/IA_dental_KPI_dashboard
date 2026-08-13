"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { Sidebar } from "./Sidebar";

interface SidebarContextValue {
  collapsed: boolean;
  toggleCollapsed: () => void;
}

const SidebarContext = createContext<SidebarContextValue | null>(null);

/**
 * Reads the collapse state set up by `AppShell`. Throws when used outside
 * it (a client leaf reading this without the provider is a bug, not a
 * degraded-but-valid state), same pattern as other single-provider hooks
 * in this codebase.
 */
export function useSidebar(): SidebarContextValue {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used within AppShell");
  }
  return context;
}

/**
 * components/shell/AppShell.tsx
 *
 * Chrome for every route under `(app)/(dashboard)/` (design "Chrome
 * placement"). Owns the sidebar collapse state in plain `useState` —
 * SPEC §3: "Estado en React (useState + contexto). No usar localStorage."
 * — so it resets on reload by design, never persisted client-side.
 *
 * This is a CLIENT component so the collapse toggle has no round-trip;
 * the layout that renders it (`(dashboard)/layout.tsx`) stays a server
 * component and only passes `children` through.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const value = useMemo<SidebarContextValue>(
    () => ({ collapsed, toggleCollapsed: () => setCollapsed((prev) => !prev) }),
    [collapsed],
  );

  return (
    <SidebarContext.Provider value={value}>
      <div className="flex min-h-screen bg-canvas">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">{children}</div>
      </div>
    </SidebarContext.Provider>
  );
}
