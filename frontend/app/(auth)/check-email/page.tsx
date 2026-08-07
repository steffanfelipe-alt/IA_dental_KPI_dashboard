import Link from "next/link";

/**
 * Static "check your email" screen (spec: "Signup pending email
 * confirmation"). Deliberately no polling — the user has to come back
 * and log in once they've confirmed, there's no client-side loop
 * waiting on backend state here.
 */
export default function CheckEmailPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-2xl font-semibold text-zinc-900">Revisá tu email</h1>
      <p className="max-w-md text-zinc-600">
        Te enviamos un link de confirmación. Una vez que confirmes tu cuenta, ya podés iniciar sesión.
      </p>
      <Link href="/login" className="font-medium text-zinc-900 underline">
        Ir a iniciar sesión
      </Link>
    </main>
  );
}
