import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ProfilePage } from "@/components/employees/profile-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Employee" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const client = await serverApi();
  const profile = client
    ? (await client.GET("/employees/{employee_id}", { params: { path: { employee_id: id } } })).data
    : undefined;
  if (!profile) notFound();
  return <ProfilePage profile={profile} />;
}
