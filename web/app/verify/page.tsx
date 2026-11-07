import type { Metadata } from "next";

import { VerifyCertificate } from "@/components/learning/verify-certificate";

export const metadata: Metadata = { title: "Check a certificate" };

export default async function Page({ searchParams }: { searchParams: Promise<{ ref?: string }> }) {
  const { ref } = await searchParams;
  return <VerifyCertificate initialRef={ref ?? ""} />;
}
