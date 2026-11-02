import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app/app-shell";
import { ChooseCompany } from "@/components/app/choose-company";
import { SessionProvider } from "@/components/app/session-context";
import { TermsGate } from "@/components/auth/terms-gate";
import { toShellSession } from "@/lib/auth/shell-session";
import { fetchMe } from "@/lib/auth/server";
import { SIDEBAR_COOKIE, parseSidebar } from "@/lib/sidebar";
import { THEME_COOKIE, parseTheme } from "@/lib/theme";

/**
 * Every signed-in page sits in the shell. The sidebar width and the colour theme come from cookies,
 * so the first paint is already right. The API says who is signed in (plan 8.1): nobody is sent to
 * sign in; someone who has not finished the second step, or who must set up two-step verification,
 * is sent to do that; someone with several companies picks one; terms not yet accepted are put in
 * front of everything. Everything below gets the person, their company and their permissions.
 */
export default async function AppLayout({ children }: Readonly<{ children: ReactNode }>) {
  const jar = await cookies();
  const me = await fetchMe();
  if (!me) redirect("/login");
  if (me.mfa === "challenge") redirect("/login/mfa");
  if (me.mfa === "enrol") redirect("/mfa/enrol");

  const session = toShellSession(me);
  if (!session) {
    const open = me.companies.filter((company) => company.status === "active");
    if (open.length === 0) redirect("/login");
    return (
      <ChooseCompany
        companies={open.map((company) => ({
          id: company.company_id,
          name: company.company_name,
          plan: company.plan === "ten_year" ? "ten-year" : company.plan,
        }))}
      />
    );
  }
  return (
    <SessionProvider me={me}>
      <AppShell
        initialCollapsed={parseSidebar(jar.get(SIDEBAR_COOKIE)?.value) === "collapsed"}
        theme={parseTheme(jar.get(THEME_COOKIE)?.value)}
        session={session}
      >
        {children}
        {me.terms_acceptance_required ? <TermsGate version={me.terms_version} /> : null}
      </AppShell>
    </SessionProvider>
  );
}
