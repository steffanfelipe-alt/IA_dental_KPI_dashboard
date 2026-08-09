import type { ReactNode } from "react";

export function IconCircle({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-24 w-24 items-center justify-center rounded-full border border-primary-200 text-primary-500">
      {children}
    </div>
  );
}
