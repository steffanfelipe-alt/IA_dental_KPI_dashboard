/**
 * app/(app)/(dashboard)/sistemas/page.tsx
 *
 * PLACEHOLDER — Pantalla B (SPEC §6: panorama, catálogo por
 * `nivelEmbudo`, `SystemMedallion`) ships in a later work unit (this
 * PR's tasks artifact: Phase 7, PR5). Exists now so the sidebar's
 * "Sistemas" link resolves to a real route instead of a 404 while this
 * PR's shell is being verified. PR5 replaces this file's body entirely,
 * at which point it should read the title from
 * `lib/copy.ts::COPY.sistemas.screenTitle` instead of this literal (kept
 * literal here on purpose — this stub predates that file in the commit
 * history, see this PR's commits).
 */
export default function SistemasPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-text-strong">Sistemas</h1>
      <p className="mt-2 text-text-body">Próximamente.</p>
    </div>
  );
}
