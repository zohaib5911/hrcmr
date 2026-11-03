import type { Metadata } from "next";
import { AttendanceAbsences } from "@/components/attendance/absence-workspace";
export const metadata: Metadata = { title: "Absences this month" };
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ month?: string }>;
}) {
  const params = await searchParams;
  return <AttendanceAbsences initialMonth={params.month} />;
}
