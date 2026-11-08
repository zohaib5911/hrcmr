import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { PlatformBar } from "@/components/platform/platform-bar";
import { hasPlatformCookie } from "@/lib/platform/session";

/**
 * Every platform admin page sits under this frame (T17.1): the red bar is always there. Without a
 * platform session (owner answer 5) the frame sends the person to start one, and comes back to the
 * page they asked for. The refusal page is the only one that does not need the session.
 */
export default async function AdminLayout({ children }: { children: ReactNode }) {
  const path = (await headers()).get("x-pathname") ?? "/";
  if (path !== "/session-required") {
    const names = (await cookies()).getAll().map((cookie) => cookie.name);
    if (!hasPlatformCookie(names)) redirect(`/session?next=${encodeURIComponent(path)}`);
  }
  return (
    <>
      <PlatformBar />
      {children}
    </>
  );
}
