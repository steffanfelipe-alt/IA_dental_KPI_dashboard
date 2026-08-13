import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";

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
 */
export default function DashboardLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
