import type { TextareaHTMLAttributes } from "react";

type FormTextareaFieldProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  error?: string;
};

/**
 * components/form/FormTextareaField.tsx
 *
 * Task 4.8 — a `components/form/*` field wrapper bound to RHF's
 * `register` (spread via `{...props}`), matching `components/ui/
 * TextField.tsx`'s visual style (label + input + inline error) but for
 * the free-text, potentially multi-line answers the guía wizard collects
 * (task 4.6). Kept minimal per orchestrator instruction: every guía
 * question is open-ended text, so this is the only field shape needed —
 * no select/checkbox wrappers are built since nothing in this batch
 * consumes them.
 */
export function FormTextareaField({ label, error, id, className = "", ...props }: FormTextareaFieldProps) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-ink-900">
        {label}
      </label>
      <textarea
        id={id}
        rows={3}
        className={`w-full rounded-xl border border-ink-400/30 px-3 py-2.5 text-sm text-ink-900 placeholder:text-ink-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100 ${className}`}
        {...props}
      />
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
    </div>
  );
}
