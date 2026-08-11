/**
 * components/veredicto/InformeText.tsx
 *
 * Minimal in-repo prose formatter for `informe.texto` (design decision:
 * "informe.texto rendered by a tiny in-repo formatter, no markdown lib" —
 * bundle/XSS surface not justified for mock LLM prose). Splits the text on
 * blank lines into blocks; a block that is a single line starting with
 * `#`/`##` followed by a space renders as a heading (H2/H3 — H1 is the
 * page's own "Veredicto" title), everything else renders as a paragraph.
 * No links, lists, bold, or other markdown syntax is interpreted —
 * `InformeResponse.texto`'s docstring (`lib/types/api.ts`) describes it as
 * "one long markdown-ish prose block", not full markdown.
 */
export function InformeText({ texto }: { texto: string }) {
  const blocks = texto
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter((block) => block.length > 0);

  return (
    <div className="flex flex-col gap-4">
      {blocks.map((block, index) => {
        const heading = parseHeading(block);
        if (heading) {
          return heading.level === 1 ? (
            <h2 key={index} className="text-lg font-semibold text-ink-900">
              {heading.text}
            </h2>
          ) : (
            <h3 key={index} className="text-base font-semibold text-ink-900">
              {heading.text}
            </h3>
          );
        }
        return (
          <p key={index} className="text-sm leading-relaxed text-ink-600">
            {block}
          </p>
        );
      })}
    </div>
  );
}

function parseHeading(block: string): { level: 1 | 2; text: string } | null {
  if (block.includes("\n")) return null;
  const match = block.match(/^(#{1,2})\s+(.+)$/);
  if (!match) return null;
  return { level: match[1].length === 1 ? 1 : 2, text: match[2] };
}
