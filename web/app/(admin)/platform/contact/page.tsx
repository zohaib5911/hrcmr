import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ContactAdmin } from "@/components/platform/contact-admin";
import { platformApi, sessionStartPath } from "@/lib/platform/guard";
import { isPlatformOwner } from "@/lib/platform/owner";

export const metadata: Metadata = {
  title: "Contact messages",
  robots: { index: false, follow: false },
};

export default async function Page() {
  const api = await platformApi();
  if (!api) redirect(sessionStartPath("/contact"));
  // An authenticated, audited read: an expired or refused platform session goes back to the start page.
  await isPlatformOwner(api, "/contact");
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <div className="mx-auto max-w-6xl">
        <ContactAdmin />
      </div>
    </main>
  );
}
