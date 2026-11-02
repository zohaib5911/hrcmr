import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PayBandsPage } from "@/components/company/pay-settings-pages";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Pay bands" };

export default async function Page() {
  const client = await serverApi();
  const bands = client ? (await client.GET("/pay-bands")).data : undefined;
  if (!bands) notFound();
  return <PayBandsPage bands={bands} />;
}
