import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { BillingPage } from "@/components/company/billing-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Billing" };

/** The company's plan (plan 8.16): the plan card, cancelling renewal and payment details. */
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ checkout?: string }>;
}) {
  const { checkout } = await searchParams;
  const client = await serverApi();
  if (!client) notFound();
  const result = await client.GET("/billing/subscription");
  // Only a Company Admin (billing.manage) gets the plan. Anyone else is told so on the page.
  if (!result.data && result.response.status !== 403) notFound();
  return (
    <BillingPage billing={result.data ?? null} checkout={checkout} now={new Date().toISOString()} />
  );
}
