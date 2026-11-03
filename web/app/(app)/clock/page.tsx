import type { Metadata } from "next";
import { AttendanceClock } from "@/components/attendance/clock";
export const metadata: Metadata = {
  title: "Clock in or out",
  manifest: "/clock/manifest.webmanifest",
};
export default function Page() {
  return <AttendanceClock />;
}
