import type { Metadata } from "next";

import { ReportsWorkspace } from "@/components/reports/workspace";

export const metadata: Metadata = { title: "Reports" };

export default function Page() {
  return <ReportsWorkspace />;
}
