import type { Metadata } from "next";

import { RotaWorkspace } from "@/components/rota/workspace";

export const metadata: Metadata = { title: "Rota" };

export default async function Page({ searchParams }: { searchParams: Promise<{ week?: string }> }) {
  return <RotaWorkspace initialWeek={(await searchParams).week} />;
}
