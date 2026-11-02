import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { HolidayManagementPage } from "@/components/company/holiday-management-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Holidays" };

export default async function Page({ searchParams }: { searchParams: Promise<{ year?: string }> }) {
  const { year } = await searchParams;
  const parsed = Number(year);
  const client = await serverApi();
  const page = client
    ? (
        await client.GET("/holiday-management", {
          params: {
            query:
              Number.isInteger(parsed) && parsed >= 2000 && parsed <= 2100 ? { year: parsed } : {},
          },
        })
      ).data
    : undefined;
  if (!page) notFound();
  return <HolidayManagementPage page={page} />;
}
