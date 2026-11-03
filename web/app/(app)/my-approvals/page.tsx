import type { Metadata } from "next";
import { LeaveHome } from "@/components/leave/home";
export const metadata: Metadata = { title: "My Approvals" };
export default function Page() {
  return <LeaveHome mode="approvals" />;
}
