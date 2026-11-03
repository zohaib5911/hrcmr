import type { Metadata } from "next";

import { WorkLogWorkspace } from "@/components/work-log/workspace";

export const metadata: Metadata = { title: "Work log" };

export default function Page() {
  return <WorkLogWorkspace />;
}
