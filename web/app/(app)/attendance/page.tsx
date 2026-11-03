import type { Metadata } from "next";
import { AttendanceWorkspace } from "@/components/attendance/workspace";
export const metadata: Metadata = { title: "Attendance" };
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);
  return (
    <AttendanceWorkspace
      employeeId={first(params.employee_id)}
      initialMonth={first(params.month)}
    />
  );
}
