"use client";

import { useId, useState, type FormEvent } from "react";
import type { CredencialSistema } from "@/lib/types";

/**
 * components/systems/CredentialItem.tsx
 *
 * Pantalla C (SPEC "Pantalla C — System Detail": "Credentials MUST show
 * only `estado`, never a `valor`; any input MUST be write-only and clear
 * immediately after submit" / scenario "Credential value never
 * rendered"). `lib/types.ts::CredencialSistema` has NO `valor` field at
 * all (SPEC §10, transcribed verbatim, "a propósito") — this component
 * only ever reads `id`/`nombre`/`estado`/`instrucciones` off its prop, so
 * there is no field to accidentally render even by mistake.
 *
 * The pending-value `<input type="password">` is local, uncontrolled-by-
 * parent state (never lifted via a prop callback into anything that
 * re-renders elsewhere), and is reset to `""` synchronously on submit —
 * Slice 2 wires the real `PUT` here (design's data flow: "onToggle
 * callbacks (Slice2 wires PUT)"), this slice has nowhere real to send it,
 * so submit only clears the field and shows a local confirmation, both
 * scoped to this component instance.
 */
const ESTADO_LABEL: Record<CredencialSistema["estado"], string> = {
  pendiente: "Pendiente",
  recibida: "Recibida",
  verificada: "Verificada",
};

const ESTADO_CLASS: Record<CredencialSistema["estado"], string> = {
  pendiente: "bg-state-bad/10 text-state-bad",
  recibida: "bg-state-flat/10 text-state-flat",
  verificada: "bg-state-good/10 text-state-good",
};

export function CredentialItem({ credencial }: { credencial: CredencialSistema }) {
  const [valor, setValor] = useState("");
  const [enviado, setEnviado] = useState(false);
  const inputId = useId();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValor("");
    setEnviado(true);
  }

  return (
    <div className="rounded-xl border border-border-subtle p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-text-strong">{credencial.nombre}</p>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${ESTADO_CLASS[credencial.estado]}`}>
          {ESTADO_LABEL[credencial.estado]}
        </span>
      </div>
      <p className="mt-1 text-xs text-text-muted">{credencial.instrucciones}</p>

      {credencial.estado === "pendiente" ? (
        <form onSubmit={handleSubmit} className="mt-2 flex items-center gap-2">
          <label htmlFor={inputId} className="sr-only">
            Valor de {credencial.nombre}
          </label>
          <input
            id={inputId}
            type="password"
            autoComplete="off"
            value={valor}
            onChange={(event) => setValor(event.target.value)}
            placeholder="Pegar valor"
            className="w-full rounded-lg border border-border-subtle px-2 py-1 text-sm text-text-body focus:outline-none focus:ring-2 focus:ring-primary-100"
          />
          <button
            type="submit"
            className="shrink-0 rounded-lg bg-primary-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-primary-700"
          >
            Enviar
          </button>
        </form>
      ) : null}

      {enviado ? <p className="mt-1 text-xs text-state-good">Enviado. Lo vamos a verificar.</p> : null}
    </div>
  );
}
