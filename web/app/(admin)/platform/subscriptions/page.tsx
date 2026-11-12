import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { SubscriptionsAdmin } from "@/components/platform/subscriptions-admin";
import { platformApi, sessionStartPath } from "@/lib/platform/guard";
import { isPlatformOwner } from "@/lib/platform/owner";

export const metadata: Metadata = {
  title: "Subscriptions",
  robots: { index: false, follow: false },
};

export default async function Page() {
  const api = await platformApi();
  if (!api) redirect(sessionStartPath("/subscriptions"));
  const isOwner = await isPlatformOwner(api, "/subscriptions");
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <div className="mx-auto max-w-6xl">
        <SubscriptionsAdmin isOwner={isOwner} />
      </div>
    </main>
  );
}
