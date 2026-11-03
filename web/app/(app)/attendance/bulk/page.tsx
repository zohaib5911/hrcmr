import type { Metadata } from "next";
import { AttendanceBulk } from "@/components/attendance/bulk-workspace";
export const metadata: Metadata = { title: "Bulk attendance" };
export default function Page() {
  return <AttendanceBulk />;
}
