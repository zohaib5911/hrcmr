import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ProfilePage } from "@/components/employees/profile-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Employee" };

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const query = await searchParams;
  const client = await serverApi();
  const request = { params: { path: { employee_id: id } } };
  const [profile, personal, employment] = client
    ? await Promise.all([
        client.GET("/employees/{employee_id}", request).then((r) => r.data),
        client.GET("/employees/{employee_id}/personal", request).then((r) => r.data),
        client.GET("/employees/{employee_id}/employment", request).then((r) => r.data),
      ])
    : [];
  if (!profile || !personal || !employment) notFound();
  return (
    <ProfilePage
      key={id + String(query.tab ?? "overview")}
      profile={profile}
      personal={personal}
      employment={employment}
      initialTab={typeof query.tab === "string" ? query.tab : "overview"}
    />
  );
}
