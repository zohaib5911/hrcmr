import type { Metadata } from "next";
import { LeaveHome } from "@/components/leave/home";
export const metadata: Metadata = { title: "My Leave" };
export default function Page() {
  return <LeaveHome mode="own" />;
}
