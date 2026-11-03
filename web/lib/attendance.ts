import type { components } from "@/lib/api/client";

export type Attendance = components["schemas"]["AttendanceOut"];
export type Status = Attendance["status"];
export type Person = components["schemas"]["EmployeeRow"];
export const STATUS: Record<Status, string> = {
  present: "Present",
  absent: "Absent",
  late: "Late",
  half_day: "Half day",
  on_leave: "On leave",
  sick: "Sick",
};

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
