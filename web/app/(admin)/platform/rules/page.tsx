import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { RulesEditor } from "@/components/platform/rules-editor";
import { serverApi } from "@/lib/auth/server";
import { AdminPage } from "@/components/platform/admin-page";

export const metadata: Metadata = {
  title: "SOC rules",
  robots: { index: false, follow: false },
};

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const { data } = await client.GET("/platform/rules");
  if (!data) notFound();
  return (
    <AdminPage>
      <RulesEditor versions={data.items} />
    </AdminPage>
  );
}
