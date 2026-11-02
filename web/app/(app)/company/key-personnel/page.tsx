import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { KeyPersonnelPage } from "@/components/company/key-personnel-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Key personnel" };

export default async function Page() {
  const client = await serverApi();
  const data = client ? (await client.GET("/key-personnel")).data : undefined;
  if (!data) notFound();
  return <KeyPersonnelPage people={data.people} rolesFilled={data.roles_filled} />;
}
