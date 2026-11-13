import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { PlatformOverview } from "@/components/platform/overview";
import { dataOrSessionRedirect, platformApi, sessionStartPath } from "@/lib/platform/guard";
import { AdminPage } from "@/components/platform/admin-page";

export const metadata: Metadata = {
  title: "Platform admin",
  robots: { index: false, follow: false },
};

export default async function PlatformAdminPage() {
  const client = await platformApi();
  if (!client) redirect(sessionStartPath("/"));
  const [metrics, queue] = await Promise.all([
    client.GET("/platform/metrics").catch(() => null),
    client.GET("/platform/jobs/queue").catch(() => null),
  ]);
  return (
    <AdminPage>
      <PlatformOverview
        metrics={metrics ? dataOrSessionRedirect(metrics, "/") : null}
        queueWaiting={queue ? (dataOrSessionRedirect(queue, "/")?.waiting ?? null) : null}
      />
    </AdminPage>
  );
}
