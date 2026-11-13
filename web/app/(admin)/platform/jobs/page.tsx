import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { JobsAdmin } from "@/components/platform/jobs-admin";
import { platformApi, dataOrSessionRedirect, sessionStartPath } from "@/lib/platform/guard";
import { PAGE_SIZE, pageOffset } from "@/lib/platform/operations";
import { AdminPage } from "@/components/platform/admin-page";
export const metadata: Metadata = { title: "Jobs", robots: { index: false, follow: false } };
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ offset?: string }>;
}) {
  const api = await platformApi();
  if (!api) redirect(sessionStartPath("/jobs"));
  const offset = pageOffset((await searchParams).offset);
  const [queue, failures] = await Promise.all([
    api.GET("/platform/jobs/queue").catch(() => null),
    api
      .GET("/platform/jobs/failures", { params: { query: { limit: PAGE_SIZE, offset } } })
      .catch(() => null),
  ]);
  return (
    <AdminPage>
      <JobsAdmin
        queue={queue ? dataOrSessionRedirect(queue, "/jobs") : null}
        failures={failures ? dataOrSessionRedirect(failures, "/jobs") : null}
        offset={offset}
      />
    </AdminPage>
  );
}
