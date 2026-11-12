import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { CompaniesList, type CompanyFilters } from "@/components/platform/companies-list";
import { platformApi, dataOrSessionRedirect, sessionStartPath } from "@/lib/platform/guard";

export const metadata: Metadata = { title: "Companies", robots: { index: false, follow: false } };
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const value = (key: string) => (typeof params[key] === "string" ? (params[key] as string) : "");
  const date = (key: string) =>
    /^\d{4}-\d{2}-\d{2}$/.test(value(key)) && !Number.isNaN(Date.parse(value(key)))
      ? value(key) + "T00:00:00Z"
      : undefined;
  const filters: CompanyFilters = {
    q: value("q").slice(0, 120) || undefined,
    plan: ["free", "annual", "ten_year"].includes(value("plan")) ? value("plan") : undefined,
    status: ["active", "suspended", "pending_deletion", "deleted"].includes(value("status"))
      ? value("status")
      : undefined,
    created_since: date("created_since"),
    active_since: date("active_since"),
    offset: Math.min(100000, Math.max(0, Math.floor(Number(value("offset")) || 0))),
  };
  const client = await platformApi();
  if (!client) redirect(sessionStartPath("/companies"));
  const result = await client
    .GET("/platform/companies", { params: { query: { ...filters, limit: 25 } } })
    .catch(() => null);
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <CompaniesList
        data={result ? dataOrSessionRedirect(result, "/companies") : null}
        filters={filters}
      />
    </main>
  );
}
