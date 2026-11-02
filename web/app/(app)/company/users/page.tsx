import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { UserAccessPage } from "@/components/company/user-access-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "User access" };

export default async function Page() {
  const client = await serverApi();
  const list = client ? (await client.GET("/users")).data : undefined;
  if (!list) notFound();
  return <UserAccessPage list={list} />;
}
