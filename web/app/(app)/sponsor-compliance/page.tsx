import type { Metadata } from "next";

import { notFound } from "next/navigation";
import { HubPage } from "@/components/compliance/hub-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Sponsor compliance" };

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const { data } = await client.GET("/compliance/overview");
  if (!data) notFound();
  return <HubPage overview={data} />;
}
