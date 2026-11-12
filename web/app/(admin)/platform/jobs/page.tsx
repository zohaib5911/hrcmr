import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { JobsAdmin } from "@/components/platform/jobs-admin";
import { platformApi, dataOrSessionRedirect, sessionStartPath } from "@/lib/platform/guard";
import { PAGE_SIZE, pageOffset } from "@/lib/platform/operations";
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
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <div className="mx-auto max-w-6xl">
        <JobsAdmin
          queue={queue ? dataOrSessionRedirect(queue, "/jobs") : null}
          failures={failures ? dataOrSessionRedirect(failures, "/jobs") : null}
          offset={offset}
        />
      </div>
    </main>
  );
}
