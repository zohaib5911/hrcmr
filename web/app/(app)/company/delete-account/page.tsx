import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DeleteAccountPage } from "@/components/company/delete-account-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Delete company account" };

/** Delete the company account (plan 8.16): what goes, an export first, the e-mailed code, withdraw. */
export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const result = await client.GET("/companies/me/deletion-request");
  // Only a Company Admin (company.delete) may. Anyone else is told so on the page.
  if (result.response.status === 403) return <DeleteAccountPage allowed={false} />;
  if (result.error) notFound();
  const overview = (await client.GET("/company")).data;
  return (
    <DeleteAccountPage
      allowed
      request={result.data ?? null}
      companyName={overview?.company.name ?? ""}
    />
  );
}
