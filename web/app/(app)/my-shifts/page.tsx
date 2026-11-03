import type { Metadata } from "next";
import { MyShifts } from "@/components/rota/my-shifts";
export const metadata: Metadata = { title: "My shifts" };
export default async function Page({ searchParams }: { searchParams: Promise<{ week?: string }> }) {
  return <MyShifts initialWeek={(await searchParams).week} />;
}
