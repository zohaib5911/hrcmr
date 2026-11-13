import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AuditAdmin } from "@/components/platform/audit-admin";
import { platformApi, dataOrSessionRedirect, sessionStartPath } from "@/lib/platform/guard";
import { auditFilters, PAGE_SIZE, pageOffset } from "@/lib/platform/operations";
import { AdminPage } from "@/components/platform/admin-page";
export const metadata: Metadata = {
  title: "Platform audit log",
  robots: { index: false, follow: false },
};
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const api = await platformApi();
  if (!api) redirect(sessionStartPath("/audit"));
  const params = await searchParams;
  const filters = auditFilters(params);
  const offset = pageOffset(typeof params.offset === "string" ? params.offset : undefined);
  const result = await api
    .GET("/platform/audit", { params: { query: { ...filters, limit: PAGE_SIZE, offset } } })
    .catch(() => null);
  return (
    <AdminPage>
      <AuditAdmin
        data={result ? dataOrSessionRedirect(result, "/audit") : null}
        filters={filters}
        offset={offset}
      />
    </AdminPage>
  );
}
