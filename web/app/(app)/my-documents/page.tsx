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
  // Reminders and policies have their own permissions (ISS-13): a People Manager may sign
  // policies without reading reminders, so a refused reminder list only hides that panel.
  const refused = response.response.status === 403;
  if (!response.data && !refused) notFound();
  const selected = Array.isArray(params.reminder) ? params.reminder[0] : params.reminder;
  const policy = Array.isArray(params.policy) ? params.policy[0] : params.policy;
  return (
    <>
      <ReceivedRemindersPage reminders={response.data ?? null} selectedId={selected} />
      <div className="mt-10">
        <OwnPolicies selectedId={policy} />
      </div>
    </>
  );
}
