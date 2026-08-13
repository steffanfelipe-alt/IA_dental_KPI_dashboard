/**
 * app/(app)/(dashboard)/panel/page.tsx
 *
 * PLACEHOLDER — Pantalla A (SPEC §5: A1/A2/A3 blocks, `MetricCard`,
 * `MetricCarousel`, anclaje) ships in a later work unit (this PR's tasks
 * artifact: Phase 4, PR2). This minimal page exists now only so the
 * `(dashboard)` shell (`AppShell` + `Sidebar`, this PR) has a real route
 * to render against — verifying the shell itself doesn't crash. PR2
 * replaces this file's body entirely, at which point it should read the
 * title from `lib/copy.ts::COPY.panel.screenTitle` instead of this
 * literal (kept literal here on purpose — this stub predates that file
 * in the commit history, see this PR's commits).
 */
export default function PanelPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-text-strong">Panel prioritario</h1>
      <p className="mt-2 text-text-body">Próximamente.</p>
    </div>
  );
}
