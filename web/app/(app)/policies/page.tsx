import type { Metadata } from "next";

import { PolicyWorkspace } from "@/components/policies/workspace";

export const metadata: Metadata = { title: "Policies" };

export default function Page() {
  return <PolicyWorkspace />;
}
