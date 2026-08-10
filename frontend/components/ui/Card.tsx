import type { ReactNode } from "react";

export function Card({ children }: { children: ReactNode }) {
  return (
    <div className="w-full max-w-sm rounded-2xl border border-black/5 bg-white p-8 shadow-sm">
      {children}
    </div>
  );
}
