import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { CompanyDetail } from "@/components/platform/company-detail";
import { platformApi, dataOrSessionRedirect, sessionStartPath } from "@/lib/platform/guard";
import { AdminPage } from "@/components/platform/admin-page";

export const metadata: Metadata = {
  title: "Company detail",
  robots: { index: false, follow: false },
};
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const path = `/companies/${encodeURIComponent(id)}`;
  const client = await platformApi();
  if (!client) redirect(sessionStartPath(path));
  const [detail, context] = await Promise.all([
    client
      .GET("/platform/companies/{company_id}", { params: { path: { company_id: id } } })
      .catch(() => null),
    client.GET("/platform/context", { params: { query: { company_id: id } } }).catch(() => null),
  ]);
  return (
    <AdminPage>
      <CompanyDetail
        company={detail ? dataOrSessionRedirect(detail, path) : null}
        context={context ? dataOrSessionRedirect(context, path) : null}
      />
    </AdminPage>
  );
}
