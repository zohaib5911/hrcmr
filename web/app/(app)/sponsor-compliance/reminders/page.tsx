import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { RemindersPage } from "@/components/compliance/reminders-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Compliance reminders" };

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const client = await serverApi();
  if (!client) notFound();
  const [register, due, history, params] = await Promise.all([
    client.GET("/compliance/reminders"),
    client.GET("/compliance/reminders/due"),
    client.GET("/compliance/reminders/history"),
    searchParams,
  ]);
  if (!register.data || !due.data || !history.data) notFound();
  const selected = Array.isArray(params.reminder) ? params.reminder[0] : params.reminder;
  return (
    <RemindersPage
      register={register.data}
      due={due.data}
      history={history.data}
      initialReminderId={selected}
    />
  );
}
