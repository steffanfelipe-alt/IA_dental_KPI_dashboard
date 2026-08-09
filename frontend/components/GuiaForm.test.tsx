// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { GuiaFormBody } from "./GuiaForm";
import type { PreguntaGuiaResponse } from "@/lib/types/api";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

const preguntas: PreguntaGuiaResponse[] = [
  {
    id: "q1",
    texto: "¿Cuántos consultorios tenés?",
    bloque: 1,
    nombre_bloque: "Infraestructura",
    nucleo: false,
    respuesta: null,
  },
  {
    id: "q2",
    texto: "¿Cómo agendás los turnos hoy?",
    bloque: 2,
    nombre_bloque: "Agenda",
    nucleo: false,
    respuesta: null,
  },
];

/**
 * Task 5.4: "Vitest: guía multi-block RHF state persists across nav,
 * single submit on finish." Drives `GuiaFormBody` directly with fixture
 * `preguntas` (task 4.6's `page.tsx`/`GuiaForm` split makes this possible
 * without mocking the initial `GET /guia` fetch — same pattern as
 * `Upload.tsx` exporting `validateFiles`).
 */
describe("GuiaFormBody (task 5.4)", () => {
  // No global Vitest setup file registers RTL's auto-cleanup in this repo
  // (see vitest.config.ts) — without this, DOM from one `it()`'s render
  // lingers into the next, causing duplicate-match errors on shared
  // labels like "Siguiente" across this file's two tests.
  afterEach(cleanup);

  beforeEach(() => {
    pushMock.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/respuestas")) {
          return new Response(null, { status: 204 });
        }
        if (url.endsWith("/estado")) {
          return new Response(JSON.stringify({ completo: true, migracion_completada: true, preguntas_faltantes: [] }), {
            status: 200,
          });
        }
        throw new Error(`Unexpected fetch call: ${url}`);
      }),
    );
  });

  it("keeps block 1's answer after navigating to block 2 and back", async () => {
    render(<GuiaFormBody clinicaId="clinic-1" preguntas={preguntas} />);

    const block1Input = screen.getByLabelText("¿Cuántos consultorios tenés?") as HTMLTextAreaElement;
    fireEvent.change(block1Input, { target: { value: "Dos consultorios" } });
    expect(block1Input.value).toBe("Dos consultorios");

    fireEvent.click(screen.getByRole("button", { name: /siguiente/i }));

    const block2Input = await screen.findByLabelText("¿Cómo agendás los turnos hoy?");
    fireEvent.change(block2Input, { target: { value: "Agenda en papel" } });

    fireEvent.click(screen.getByRole("button", { name: /atrás/i }));

    const block1InputAgain = (await screen.findByLabelText(
      "¿Cuántos consultorios tenés?",
    )) as HTMLTextAreaElement;
    expect(block1InputAgain.value).toBe("Dos consultorios");
  });

  it("sends exactly one PUT with the full answer map on the final submit, then refetches estado and routes to estado", async () => {
    render(<GuiaFormBody clinicaId="clinic-1" preguntas={preguntas} />);

    fireEvent.change(screen.getByLabelText("¿Cuántos consultorios tenés?"), {
      target: { value: "Dos consultorios" },
    });
    fireEvent.click(screen.getByRole("button", { name: /siguiente/i }));

    const block2Input = await screen.findByLabelText("¿Cómo agendás los turnos hoy?");
    fireEvent.change(block2Input, { target: { value: "Agenda en papel" } });

    fireEvent.click(screen.getByRole("button", { name: /finalizar/i }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledTimes(1));
    expect(pushMock).toHaveBeenCalledWith("/onboarding/clinic-1/estado");

    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    const putCalls = fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "PUT");
    expect(putCalls).toHaveLength(1);

    const [putUrl, putInit] = putCalls[0] as [string, RequestInit];
    expect(putUrl).toBe("/api/clinicas/clinic-1/respuestas");
    expect(JSON.parse(putInit.body as string)).toEqual({
      respuestas: { q1: "Dos consultorios", q2: "Agenda en papel" },
    });

    const estadoCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/estado"));
    expect(estadoCalls).toHaveLength(1);
  });
});
