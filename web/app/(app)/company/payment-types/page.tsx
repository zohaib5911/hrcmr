import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PaymentTypesPage } from "@/components/company/pay-settings-pages";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Payment types" };

export default async function Page() {
  const client = await serverApi();
  const types = client ? (await client.GET("/payment-types")).data : undefined;
  if (!types) notFound();
  return <PaymentTypesPage types={types} />;
}
