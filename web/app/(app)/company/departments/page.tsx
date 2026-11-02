import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DepartmentsPage } from "@/components/company/departments-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Departments" };

export default async function Page() {
  const client = await serverApi();
  const departments = client ? (await client.GET("/departments")).data : undefined;
  if (!departments) notFound();
  return <DepartmentsPage departments={departments} />;
}
