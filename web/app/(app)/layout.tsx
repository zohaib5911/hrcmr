import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app/app-shell";
import { TermsGate } from "@/components/auth/terms-gate";
import { fetchMe } from "@/lib/auth/server";
import { SIDEBAR_COOKIE, parseSidebar } from "@/lib/sidebar";
import { THEME_COOKIE, parseTheme } from "@/lib/theme";

/**
 * Every signed-in page sits in the shell. The sidebar width and the colour theme come from cookies,
 * so the first paint is already right. Before anything is shown, someone who has not finished
 * signing in (second step, or a required set-up of two-step verification) is sent to do that, and
 * terms they have not accepted are put in front of everything. The session itself (company, person,
 * permissions) is supplied by T3.4.
 */
export default async function AppLayout({ children }: Readonly<{ children: ReactNode }>) {
  const jar = await cookies();
  const me = await fetchMe();
  if (me?.mfa === "challenge") redirect("/login/mfa");
  if (me?.mfa === "enrol") redirect("/mfa/enrol");
  return (
    <AppShell
      initialCollapsed={parseSidebar(jar.get(SIDEBAR_COOKIE)?.value) === "collapsed"}
      theme={parseTheme(jar.get(THEME_COOKIE)?.value)}
      session={null}
    >
      {children}
      {me?.terms_acceptance_required ? <TermsGate version={me.terms_version} /> : null}
    </AppShell>
  );
}
