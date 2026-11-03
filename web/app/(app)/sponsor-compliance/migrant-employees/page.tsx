import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SponsoredEmployeesPage } from "@/components/compliance/sponsored-employees-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Sponsored employees" };

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const { data } = await client.GET("/compliance/sponsored-employees");
  if (!data) notFound();
  return <SponsoredEmployeesPage employees={data.employees} />;
}
