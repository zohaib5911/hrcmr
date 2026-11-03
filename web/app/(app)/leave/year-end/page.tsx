import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { YearEndPage } from "@/components/leave/year-end-page";
import { serverApi } from "@/lib/auth/server";
export const metadata: Metadata = { title: "Leave year end" };
export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const response = await client.GET("/leave/settings");
  if (!response.data) notFound();
  return <YearEndPage startMonthDay={response.data.leave_year_start_month_day} />;
}
