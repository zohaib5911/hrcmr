import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DesignationsPage } from "@/components/company/designations-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Designations" };

export default async function Page() {
  const client = await serverApi();
  const designations = client ? (await client.GET("/designations")).data : undefined;
  const departments = client ? (await client.GET("/departments")).data : undefined;
  if (!designations || !departments) notFound();
  return <DesignationsPage designations={designations} departments={departments} />;
}
