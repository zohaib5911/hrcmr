import { cookies } from "next/headers";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app/app-shell";
import { SIDEBAR_COOKIE, parseSidebar } from "@/lib/sidebar";
import { THEME_COOKIE, parseTheme } from "@/lib/theme";

/**
 * Every signed-in page sits in the shell. The sidebar width and the colour theme come from cookies,
 * so the first paint is already right. The session (company, person, permissions) is supplied by
 * the sign-in work in T3.4; until then the company and person show as loading placeholders.
 */
export default async function AppLayout({ children }: Readonly<{ children: ReactNode }>) {
  const jar = await cookies();
  return (
    <AppShell
      initialCollapsed={parseSidebar(jar.get(SIDEBAR_COOKIE)?.value) === "collapsed"}
      theme={parseTheme(jar.get(THEME_COOKIE)?.value)}
      session={null}
    >
      {children}
    </AppShell>
  );
}
