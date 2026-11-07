import type { Metadata } from "next";

import { RecruitmentWorkspace } from "@/components/recruitment/workspace";

export const metadata: Metadata = { title: "Recruitment" };

export default function Page() {
  return <RecruitmentWorkspace />;
}
