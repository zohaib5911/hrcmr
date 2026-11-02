import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { TaxCodesPage } from "@/components/company/pay-settings-pages";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Tax codes" };

export default async function Page() {
  const client = await serverApi();
  const codes = client ? (await client.GET("/tax-codes")).data : undefined;
  if (!codes) notFound();
  return <TaxCodesPage codes={codes} />;
}
