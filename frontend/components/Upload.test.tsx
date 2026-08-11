// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Upload } from "./Upload";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

function makeFile(name: string): File {
  return new File([new Uint8Array(10)], name, { type: "application/pdf" });
}

function selectFile(container: HTMLElement, file: File) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) {
    throw new Error("file input not found");
  }
  fireEvent.change(input, { target: { files: [file] } });
}

/**
 * Spec "onboarding-upload-feedback": full-screen `LoadingScreen` for the
 * whole `/migrar` request, not just a disabled button. `Upload.test.ts`
 * (`.ts`, no JSX) keeps covering `validateFiles`'s pre-validation; this
 * file covers the component's render/submit behavior.
 */
describe("Upload — extended-wait loading feedback (spec onboarding-upload-feedback)", () => {
  afterEach(cleanup);

  beforeEach(() => {
    pushMock.mockReset();
  });

  it("replaces the form with a full-screen LoadingScreen while submitting is true, then routes to guía on success", async () => {
    let resolveMigrar!: (value: Response) => void;
    const migrarPromise = new Promise<Response>((resolve) => {
      resolveMigrar = resolve;
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/migrar")) {
          return migrarPromise;
        }
        if (url.endsWith("/estado")) {
          return new Response(
            JSON.stringify({ completo: false, migracion_completada: true, preguntas_faltantes: [] }),
            { status: 200 },
          );
        }
        throw new Error(`Unexpected fetch call: ${url}`);
      }),
    );

    const { container } = render(<Upload clinicaId="clinic-1" />);

    selectFile(container, makeFile("planilla.pdf"));
    fireEvent.click(screen.getByRole("button", { name: /subir y continuar/i }));

    // While the migrar request is in flight, the form is gone and the
    // full-screen loading state (with its "might take a while" copy) is up.
    await screen.findByText("Esto puede tardar un momento…");
    expect(screen.queryByText("Subí tus archivos")).toBeNull();

    resolveMigrar(new Response(JSON.stringify({ variables: {} }), { status: 200 }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/onboarding/clinic-1/guia"));
  });

  it("routes to conflictos instead when the migrar response carries conflictos_pendientes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/migrar")) {
          return new Response(
            JSON.stringify({ variables: {}, conflictos_pendientes: [{ variable: "turnos_agendados" }] }),
            { status: 200 },
          );
        }
        if (url.endsWith("/estado")) {
          return new Response(
            JSON.stringify({ completo: false, migracion_completada: true, preguntas_faltantes: [] }),
            { status: 200 },
          );
        }
        throw new Error(`Unexpected fetch call: ${url}`);
      }),
    );

    const { container } = render(<Upload clinicaId="clinic-1" />);

    selectFile(container, makeFile("planilla.pdf"));
    fireEvent.click(screen.getByRole("button", { name: /subir y continuar/i }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/onboarding/clinic-1/conflictos"));
  });

  it("dismisses the loading state and re-renders the form with an error message when migrar fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/migrar")) {
          return new Response(
            JSON.stringify({ error: { codigo: 422, mensaje: "No se pudo procesar el archivo." } }),
            { status: 422 },
          );
        }
        throw new Error(`Unexpected fetch call: ${url}`);
      }),
    );

    const { container } = render(<Upload clinicaId="clinic-1" />);

    selectFile(container, makeFile("planilla.pdf"));
    fireEvent.click(screen.getByRole("button", { name: /subir y continuar/i }));

    await screen.findByText("No se pudo procesar el archivo.");
    expect(screen.getByText("Subí tus archivos")).toBeTruthy();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
