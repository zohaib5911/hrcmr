import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { SubscriptionsAdmin } from "@/components/platform/subscriptions-admin";
import { platformApi, sessionStartPath } from "@/lib/platform/guard";
import { isPlatformOwner } from "@/lib/platform/owner";
import { AdminPage } from "@/components/platform/admin-page";

export const metadata: Metadata = {
  title: "Subscriptions",
  robots: { index: false, follow: false },
};

export default async function Page() {
  const api = await platformApi();
  if (!api) redirect(sessionStartPath("/subscriptions"));
  const isOwner = await isPlatformOwner(api, "/subscriptions");
  return (
    <AdminPage>
      <SubscriptionsAdmin isOwner={isOwner} />
    </AdminPage>
  );
}
