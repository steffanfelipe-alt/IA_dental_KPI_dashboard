/**
 * lib/searchParams.ts
 *
 * Plain (no `"use client"`) home for shareable `?param=` search-param
 * KEYS read by a Server Component page and written back by a client
 * control via `router.push`.
 *
 * Real bug found and fixed in PR5: `PeriodPicker.tsx` (PR1) originally
 * defined AND exported `PERIODO_SEARCH_PARAM` from its own `"use client"`
 * file, and `panel/page.tsx` (a Server Component) imported that constant
 * directly from the client module. Next's RSC bundler wraps EVERY export
 * of a `"use client"` file in an opaque client-reference proxy when it
 * crosses the server/client boundary — not just component exports — so
 * the Server Component received a reference object instead of the
 * literal string `"periodo"`. `params[PERIODO_SEARCH_PARAM]` then never
 * matched the real query key, and `?periodo=` silently did nothing.
 *
 * Confirmed live against a production `next build && next start` (not
 * just dev-mode HMR, to rule out a Turbopack dev cache): `await
 * searchParams` correctly resolved to `{"periodo":"6m"}` for a
 * `?periodo=6m` request, `Object.keys(params)` correctly listed
 * `["periodo"]`, yet `params[PERIODO_SEARCH_PARAM]` was `undefined`.
 * `MetricTypeFilter.tsx` (this PR, task 7.2) hit the identical shape
 * before this fix, with `AGRUPACION_SEARCH_PARAM`.
 *
 * Fix: keep search-param KEY constants in a plain module with no
 * `"use client"` directive, imported directly by both the Server
 * Component page and the client control. Never import a search-param
 * key (or any other runtime value meant for plain use, not JSX) from a
 * `"use client"` file into server code again — see this file's own
 * import sites (`panel/page.tsx`, `sistemas/page.tsx`,
 * `PeriodPicker.tsx`, `MetricTypeFilter.tsx`) for the corrected pattern.
 */
export const PERIODO_SEARCH_PARAM = "periodo";
export const AGRUPACION_SEARCH_PARAM = "agrupacion";
