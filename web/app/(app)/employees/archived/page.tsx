import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { EmployeesPage } from "@/components/employees/employees-page";
import { serverApi } from "@/lib/auth/server";
import { allEmployees } from "@/lib/employees/list";

export const metadata: Metadata = { title: "Archived employees" };

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const [list, summary] = await Promise.all([
    allEmployees(client, { status: "archived" }),
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
