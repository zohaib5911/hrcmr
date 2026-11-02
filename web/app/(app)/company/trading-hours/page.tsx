import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { TradingHoursPage } from "@/components/company/trading-hours-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Trading hours" };

export default async function Page() {
  const client = await serverApi();
  const hours = client ? (await client.GET("/trading-hours")).data : undefined;
  if (!hours) notFound();
  return <TradingHoursPage hours={hours} />;
}
