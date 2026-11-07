import type { Metadata } from "next";

import { OrgChartWorkspace } from "@/components/organogram/workspace";

export const metadata: Metadata = { title: "Org chart" };

export default function Page() {
  return <OrgChartWorkspace />;
}
