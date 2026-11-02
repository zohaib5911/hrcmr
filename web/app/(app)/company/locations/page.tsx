import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { LocationsPage } from "@/components/company/locations-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Locations" };

export default async function Page() {
  const client = await serverApi();
  const locations = client ? (await client.GET("/locations")).data : undefined;
  if (!locations) notFound();
  return <LocationsPage locations={locations} />;
}
