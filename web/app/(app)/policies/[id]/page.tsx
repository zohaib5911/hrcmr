import type { Metadata } from "next";

import { PolicyDetail } from "@/components/policies/detail";

export const metadata: Metadata = { title: "Policy" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PolicyDetail policyId={id} />;
}
