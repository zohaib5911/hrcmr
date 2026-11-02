import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { UserAccessPage } from "@/components/company/user-access-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "User access" };

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const [list, policy, matrix] = await Promise.all([
    client.GET("/users"),
    client.GET("/security/two-step"),
    client.GET("/roles/matrix"),
  ]);
  if (!list.data || !policy.data || !matrix.data) notFound();
  return <UserAccessPage list={list.data} policy={policy.data} matrix={matrix.data} />;
}
