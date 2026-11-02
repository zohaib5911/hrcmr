import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { BankAccountsPage } from "@/components/company/pay-settings-pages";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Bank accounts" };

export default async function Page() {
  const client = await serverApi();
  const accounts = client ? (await client.GET("/bank-accounts")).data : undefined;
  if (!accounts) notFound();
  return <BankAccountsPage accounts={accounts} />;
}
