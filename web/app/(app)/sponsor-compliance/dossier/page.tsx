import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DossierPage } from "@/components/compliance/dossier-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Sponsor Management Dossier" };

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const { data } = await client.GET("/compliance/dossier");
  if (!data) notFound();
  return <DossierPage dossier={data} />;
}
