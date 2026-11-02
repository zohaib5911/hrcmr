import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ProfilePage } from "@/components/employees/profile-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Employee" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const client = await serverApi();
  const request = { params: { path: { employee_id: id } } };
  const [profile, personal] = client
    ? await Promise.all([
        client.GET("/employees/{employee_id}", request).then((r) => r.data),
        client.GET("/employees/{employee_id}/personal", request).then((r) => r.data),
      ])
    : [];
  if (!profile || !personal) notFound();
  return <ProfilePage profile={profile} personal={personal} />;
}
