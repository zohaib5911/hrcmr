import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { UsersAdmin } from "@/components/platform/users-admin";
import { platformApi, sessionStartPath } from "@/lib/platform/guard";

export const metadata: Metadata = {
  title: "Users",
  robots: { index: false, follow: false },
};

export default async function Page() {
  // The search runs in the browser; the page only needs a platform session to be started.
  if (!(await platformApi())) redirect(sessionStartPath("/users"));
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <div className="mx-auto max-w-6xl">
        <UsersAdmin />
      </div>
    </main>
  );
}
