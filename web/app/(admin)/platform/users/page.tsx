import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { UsersAdmin } from "@/components/platform/users-admin";
import { platformApi, sessionStartPath } from "@/lib/platform/guard";
import { isPlatformOwner } from "@/lib/platform/owner";
import { AdminPage } from "@/components/platform/admin-page";

export const metadata: Metadata = {
  title: "Users",
  robots: { index: false, follow: false },
};

export default async function Page() {
  // The search runs in the browser; the page only needs a platform session to be started.
  const api = await platformApi();
  if (!api) redirect(sessionStartPath("/users"));
  // An authenticated, audited read: an expired or refused platform session goes back to the start page.
  await isPlatformOwner(api, "/users");
  return (
    <AdminPage>
      <UsersAdmin />
    </AdminPage>
  );
}
