import { redirect } from "next/navigation";
import { hasAccessCookie } from "@/lib/bff/sessionCookies";

/**
 * D1d — server-side session gate for every route under `(app)`. This is
 * a cheap PRESENCE check ("is there an access cookie at all"), not a
 * token verifier: real validation is deferred to the first proxied
 * `callApi` call from whatever page renders inside this layout, via the
 * D1b refresh-or-401 flow. An expired-but-present cookie still passes
 * this gate and gets caught (and silently refreshed, or bounced to
 * /login) the moment a page actually calls the backend.
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const hasSession = await hasAccessCookie();
  if (!hasSession) {
    redirect("/login");
  }

  return <>{children}</>;
}
