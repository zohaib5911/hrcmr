import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { LeaveSettingsPage } from "@/components/leave/settings-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Leave settings" };

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const [settings, types] = await Promise.all([
    client.GET("/leave/settings"),
    client.GET("/leave/types"),
  ]);
  if (!settings.data || !types.data) notFound();
  return <LeaveSettingsPage settings={settings.data} types={types.data} />;
}
