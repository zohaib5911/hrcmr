import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ChangesPage } from "@/components/compliance/changes-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Change of circumstances" };

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const [changes, organisation] = await Promise.all([
    client.GET("/compliance/changes"),
    client.GET("/compliance/org-changes"),
  ]);
  if (!changes.data || !organisation.data) notFound();
  return <ChangesPage changes={changes.data} organisation={organisation.data} />;
}
