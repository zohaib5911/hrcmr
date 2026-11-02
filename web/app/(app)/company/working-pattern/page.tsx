import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { WorkingPatternPage } from "@/components/company/working-pattern-page";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Working pattern" };

export default async function Page() {
  const client = await serverApi();
  const pattern = client ? (await client.GET("/working-pattern")).data : undefined;
  if (!pattern) notFound();
  return <WorkingPatternPage pattern={pattern} />;
}
