import { describe, expect, it } from "vitest";
import { validateFiles } from "./Upload";

// api/config.py: TAMANO_MAXIMO_ARCHIVO_BYTES = 20MB, EXTENSIONES_PERMITIDAS
// = {".xlsx", ".xls", ".csv", ".pdf", ".jpg", ".jpeg", ".png"}.
const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024;

function makeFile(name: string, sizeBytes: number): File {
  // A real Blob of that byte length so `.size` reflects it without
  // allocating actual content — jsdom's File/Blob honor a Blob part's length.
  const content = new Uint8Array(sizeBytes);
  return new File([content], name);
}

describe("validateFiles (task 5.3 — client pre-validation, no network call)", () => {
  it("accepts files within the size limit and an allowed extension", () => {
    const file = makeFile("planilla.xlsx", 1024);
    expect(validateFiles([file])).toBeNull();
  });

  it("accepts every allowed extension", () => {
    for (const ext of [".xlsx", ".xls", ".csv", ".pdf", ".jpg", ".jpeg", ".png"]) {
      expect(validateFiles([makeFile(`archivo${ext}`, 1024)])).toBeNull();
    }
  });

  it("rejects a disallowed extension before any network call could happen", () => {
    const file = makeFile("nota.docx", 1024);
    const result = validateFiles([file]);
    expect(result).toMatch(/no es un formato admitido/);
  });

  it("rejects a file over the 20MB limit", () => {
    const file = makeFile("grande.pdf", MAX_FILE_SIZE_BYTES + 1);
    const result = validateFiles([file]);
    expect(result).toMatch(/supera el tamaño máximo/);
  });

  it("accepts a file exactly at the 20MB limit", () => {
    const file = makeFile("justo.pdf", MAX_FILE_SIZE_BYTES);
    expect(validateFiles([file])).toBeNull();
  });

  it("rejects the whole batch if any single file is invalid", () => {
    const good = makeFile("ok.pdf", 1024);
    const bad = makeFile("mala.txt", 1024);
    expect(validateFiles([good, bad])).toMatch(/no es un formato admitido/);
  });
});
