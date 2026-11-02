import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ComplianceDocumentsPage } from "@/components/company/compliance-documents-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Compliance documents" };

export default async function Page() {
  const client = await serverApi();
  const data = client ? (await client.GET("/compliance-documents")).data : undefined;
  if (!data) notFound();
  return <ComplianceDocumentsPage slots={data.slots} filled={data.filled} total={data.total} />;
}
