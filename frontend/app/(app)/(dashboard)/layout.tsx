import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { AnclajeProvider } from "@/lib/anclaje/AnclajeContext";

/**
 * app/(app)/(dashboard)/layout.tsx
 *
 * NEW nested route group (design "Chrome placement" decision), not a
 * change to `(app)/layout.tsx`. That outer layout is the session gate
 * shared by onboarding, veredicto, and this dashboard — adding the
 * sidebar chrome there would regress onboarding's chrome-less pages.
 * Nesting here scopes `AppShell`/`Sidebar` to `/panel`, `/sistemas`, and
 * their sub-routes only; `(app)/layout.tsx`'s gate still runs first
 * (Next.js composes parent layouts), unmodified.
 *
 * `AnclajeProvider` (task 5.2) wraps `AppShell` here — not inside it —
 * so the anchoring store is shared across every route this layout scopes
 * (`/panel` AND `/sistemas`), per SPEC "Manual System Anchoring (A3-bis)".
 * This file stays a server component; `AnclajeProvider` is its own
 * `"use client"` boundary, same pattern as passing `AppShell` through.
 */
export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AnclajeProvider>
      <AppShell>{children}</AppShell>
    </AnclajeProvider>
  );
}
