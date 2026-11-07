import type { Metadata } from "next";

import { ApplicationPage } from "@/components/recruitment/application-page";

export const metadata: Metadata = { title: "Application" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ApplicationPage applicationId={id} />;
}
