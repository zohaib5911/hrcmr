import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { PlatformOverview } from "@/components/platform/overview";
import { serverApi } from "@/lib/auth/server";
import { dataOrSessionRedirect, sessionStartPath } from "@/lib/platform/guard";

export const metadata: Metadata = {
  title: "Platform admin",
  robots: { index: false, follow: false },
};

export default async function PlatformAdminPage() {
  const client = await serverApi();
  if (!client) redirect(sessionStartPath("/"));
  const [metrics, queue] = await Promise.all([
    client.GET("/platform/metrics").catch(() => null),
    client.GET("/platform/jobs/queue").catch(() => null),
  ]);
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <PlatformOverview
        metrics={metrics ? dataOrSessionRedirect(metrics, "/") : null}
        queueWaiting={queue ? (dataOrSessionRedirect(queue, "/")?.waiting ?? null) : null}
      />
    </main>
  );
}
