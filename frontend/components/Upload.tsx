"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { isApiErrorEnvelope } from "@/lib/types/errors";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { MigrarResponse } from "@/lib/types/api";

// api/config.py: TAMANO_MAXIMO_ARCHIVO_BYTES / EXTENSIONES_PERMITIDAS —
// mirrored here so bad files are rejected before any network call
// (spec "File Upload" + D6 client pre-validation), not guessed.
const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".xlsx", ".xls", ".csv", ".pdf", ".jpg", ".jpeg", ".png"];

function getExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot).toLowerCase();
}

/** Exported for the pre-validation unit test (task 5.3). */
export function validateFiles(files: File[]): string | null {
  for (const file of files) {
    if (!ALLOWED_EXTENSIONS.includes(getExtension(file.name))) {
      return `"${file.name}" no es un formato admitido. Usá .xlsx, .xls, .csv, .pdf, .jpg, .jpeg o .png.`;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return `"${file.name}" supera el tamaño máximo de 20MB.`;
    }
  }
  return null;
}

function UploadCloudIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-6 w-6"
    >
      <path d="M7 18a4 4 0 0 1-1-7.9 5 5 0 0 1 9.6-2A4.5 4.5 0 0 1 17 18" />
      <path d="M12 12v7M9.5 14.5 12 12l2.5 2.5" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

/**
 * Spec "File Upload": client pre-validates (20MB / allowed extensions)
 * before submit, forwards a `POST` to the BFF's `migrar` route (which
 * forwards `FormData` untouched to `POST /onboarding/{id}/migrar`, field
 * name `archivos` per `api/routers/onboarding.py`), refetches `estado`
 * per D7, then routes to conflicts (if the migrar response carries
 * `conflictos_pendientes`) or straight to the guide.
 */
export function Upload({ clinicaId }: { clinicaId: string }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  /**
   * Adds to the current selection rather than replacing it — the input
   * has `multiple`, but users also reopen the picker (or drop again) to
   * add more files in separate batches, and each batch should stack.
   */
  function addFiles(selected: FileList | null) {
    setError(null);
    if (!selected || selected.length === 0) {
      return;
    }
    const incoming = Array.from(selected);
    const validationError = validateFiles(incoming);
    if (validationError) {
      setError(validationError);
      return;
    }
    setFiles((prev) => {
      const existingKeys = new Set(prev.map((file) => `${file.name}-${file.size}`));
      const deduped = incoming.filter((file) => !existingKeys.has(`${file.name}-${file.size}`));
      return [...prev, ...deduped];
    });
  }

  function handleInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    addFiles(event.target.files);
    // Reset so picking the exact same file again still fires onChange.
    event.target.value = "";
  }

  function handleDrop(event: React.DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragging(false);
    addFiles(event.dataTransfer.files);
  }

  function handleDragOver(event: React.DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave() {
    setIsDragging(false);
  }

  function handleRemove(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit() {
    if (files.length === 0) {
      setError("Seleccioná al menos un archivo.");
      return;
    }

    setSubmitting(true);
    setError(null);

    const formData = new FormData();
    files.forEach((file) => formData.append("archivos", file));

    const response = await fetch(`/api/clinicas/${clinicaId}/migrar`, {
      method: "POST",
      body: formData,
    });

    const body: unknown = await response.json().catch(() => null);

    if (!response.ok) {
      const mensaje = isApiErrorEnvelope(body) ? body.error.mensaje : "No se pudieron subir los archivos.";
      setError(mensaje);
      setSubmitting(false);
      return;
    }

    // Spec/D7: estado MUST be refetched after every mutation, including
    // upload — even though the routing decision below relies on this same
    // migrar response's own `conflictos_pendientes`, not on estado.
    await fetch(`/api/clinicas/${clinicaId}/estado`, { cache: "no-store" });

    setSubmitting(false);

    const resultado = body as MigrarResponse;
    if (resultado.conflictos_pendientes && resultado.conflictos_pendientes.length > 0) {
      // The backend never persists `conflictos_pendientes` — it only ever
      // appears in this response body (see `parser/pipeline.py`'s
      // `procesar_migracion`/`resolver_conflicto`, both return it inline,
      // with no corresponding GET route). `conflictos/page.tsx` is a fresh
      // navigation with no props from here, so `sessionStorage` is the
      // bridge that carries the list across that navigation; the
      // conflicts page reads and clears this same key on mount.
      sessionStorage.setItem(`onboarding:conflictos:${clinicaId}`, JSON.stringify(resultado.conflictos_pendientes));
      router.push(`/onboarding/${clinicaId}/conflictos`);
      return;
    }
    router.push(`/onboarding/${clinicaId}/guia`);
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <Card>
        <div className="space-y-6">
          <h1 className="text-2xl font-semibold text-ink-900">Subí tus archivos</h1>
          <p className="text-sm text-ink-600">
            Planillas (.xlsx, .xls, .csv), PDFs o fotos (.jpg, .jpeg, .png) de hasta 20MB cada uno.
          </p>

          {error ? (
            <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          ) : null}

          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`flex w-full flex-col items-center gap-2 rounded-2xl border-2 border-dashed px-4 py-8 text-center transition-colors ${
              isDragging ? "border-primary-400 bg-primary-50" : "border-primary-200 bg-primary-50/40 hover:border-primary-300"
            }`}
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-50 text-primary-500">
              <UploadCloudIcon />
            </span>
            <span className="text-sm font-medium text-ink-900">
              Arrastrá tus archivos acá o hacé clic para elegirlos
            </span>
            <span className="text-xs text-ink-400">.xlsx, .xls, .csv, .pdf, .jpg, .jpeg, .png — máx. 20MB</span>
          </button>

          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ALLOWED_EXTENSIONS.join(",")}
            className="hidden"
            onChange={handleInputChange}
          />

          {files.length > 0 ? (
            <ul className="space-y-2">
              {files.map((file, index) => (
                <li
                  key={`${file.name}-${index}`}
                  className="flex items-center justify-between gap-2 rounded-xl border border-ink-400/20 px-3 py-2 text-sm text-ink-900"
                >
                  <span className="truncate">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => handleRemove(index)}
                    className="shrink-0 text-ink-400 hover:text-ink-600"
                    aria-label={`Quitar ${file.name}`}
                  >
                    <CloseIcon />
                  </button>
                </li>
              ))}
            </ul>
          ) : null}

          <Button type="button" onClick={handleSubmit} disabled={submitting || files.length === 0}>
            {submitting ? "Subiendo…" : "Subir y continuar"}
          </Button>
        </div>
      </Card>
    </main>
  );
}
