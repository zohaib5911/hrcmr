import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ContactAdmin } from "@/components/platform/contact-admin";
import { platformApi, sessionStartPath } from "@/lib/platform/guard";

export const metadata: Metadata = {
  title: "Contact messages",
  robots: { index: false, follow: false },
};

export default async function Page() {
  // The lists load in the browser; the page only needs a platform session to be started.
  if (!(await platformApi())) redirect(sessionStartPath("/contact"));
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <div className="mx-auto max-w-6xl">
        <ContactAdmin />
      </div>
    </main>
  );
}
