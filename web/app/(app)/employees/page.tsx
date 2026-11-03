import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { EmployeesPage } from "@/components/employees/employees-page";
import { serverApi } from "@/lib/auth/server";
import { rtwFilterFromParam } from "@/lib/employees/rtw";
import { pillFromParam } from "@/lib/employees/list";

export const metadata: Metadata = { title: "Employees" };

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const client = await serverApi();
  if (!client) notFound();
  const [list, summary, params] = await Promise.all([
    client.GET("/employees"),
    client.GET("/employees/summary"),
    searchParams,
  ]);
  if (!list.data || !summary.data) notFound();
  return (
    <EmployeesPage
      employees={list.data.employees}
      summary={summary.data}
      archived={false}
      initialPill={pillFromParam(params.status)}
      initialRtw={rtwFilterFromParam(params.rtw)}
    />
  );
}
