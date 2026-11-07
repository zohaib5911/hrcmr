import type { Metadata } from "next";

import { LearningWorkspace } from "@/components/learning/workspace";

export const metadata: Metadata = { title: "Learning" };

export default function Page() {
  return <LearningWorkspace />;
}
