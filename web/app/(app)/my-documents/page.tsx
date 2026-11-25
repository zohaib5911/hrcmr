import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { OwnPolicies } from "@/components/policies/own-documents";
import { ReceivedRemindersPage } from "@/components/compliance/received-reminders-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "My documents" };

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const client = await serverApi();
  if (!client) notFound();
  const [response, params] = await Promise.all([
    client.GET("/me/document-reminders"),
    searchParams,
  ]);
  if (!response.data) notFound();
  const selected = Array.isArray(params.reminder) ? params.reminder[0] : params.reminder;
  const policy = Array.isArray(params.policy) ? params.policy[0] : params.policy;
  return (
    <>
      <ReceivedRemindersPage reminders={response.data} selectedId={selected} />
      <div className="mt-10">
        <OwnPolicies selectedId={policy} />
      </div>
    </>
  );
}
