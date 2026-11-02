import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { EmployeesPage } from "@/components/employees/employees-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Archived employees" };

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const [list, summary] = await Promise.all([
    client.GET("/employees", { params: { query: { status: "archived" } } }),
    client.GET("/employees/summary"),
  ]);
  if (!list.data || !summary.data) notFound();
  return (
    <EmployeesPage
      employees={list.data.employees}
      summary={summary.data}
      archived
      initialPill="all"
    />
  );
}
