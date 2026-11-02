import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";
import { CompanyOverview } from "@/components/company/company-overview";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Company" };

export default async function Page() {
  const client = await serverApi();
  const overview = client ? (await client.GET("/company")).data : undefined;
  // Without it (the API is down, or the person may not see it) the page says what it is for.
  if (!overview) return <PlaceholderPage id="company" />;
  const options = (await client?.GET("/company/options"))?.data ?? null;
  return <CompanyOverview overview={overview} options={options} />;
}
