import Link from "next/link";
import { IconCircle } from "@/components/ui/IconCircle";

/**
 * Static "check your email" screen (spec: "Signup pending email
 * confirmation"). Deliberately no polling — the user has to come back
 * and log in once they've confirmed, there's no client-side loop
 * waiting on backend state here.
 */
export default function CheckEmailPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8 text-center">
      <IconCircle>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-10 w-10"
        >
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <path d="m4 7 8 6 8-6" />
        </svg>
      </IconCircle>

      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-ink-900">Revisá tu email</h1>
        <p className="max-w-md text-ink-600">
          Te enviamos un link de confirmación. Una vez que confirmes tu cuenta, ya podés iniciar sesión.
        </p>
      </div>

      <Link href="/login" className="font-medium text-primary-600 hover:text-primary-700">
        Ir a iniciar sesión
      </Link>
    </main>
  );
}
