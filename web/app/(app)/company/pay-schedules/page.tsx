import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PaySchedulesPage } from "@/components/company/pay-settings-pages";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Pay schedules" };

export default async function Page() {
  const client = await serverApi();
  const schedules = client ? (await client.GET("/pay-schedules")).data : undefined;
  if (!schedules) notFound();
  return <PaySchedulesPage schedules={schedules} />;
}
