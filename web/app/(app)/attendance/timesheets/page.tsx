import type { Metadata } from "next";
import { AttendanceTimesheets } from "@/components/attendance/timesheets";
export const metadata: Metadata = { title: "Timesheet approvals" };
export default function Page() {
  return <AttendanceTimesheets />;
}
