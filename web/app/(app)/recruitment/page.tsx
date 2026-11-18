import type { Metadata } from "next";

import { RECRUITMENT_TABS, type RecruitmentTab } from "@/components/recruitment/tabs";
import { RecruitmentWorkspace } from "@/components/recruitment/workspace";

export const metadata: Metadata = { title: "Recruitment" };

export default async function Page({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
  const { tab } = await searchParams;
  const initialTab = RECRUITMENT_TABS.find((name) => name === tab) as RecruitmentTab | undefined;
  return <RecruitmentWorkspace {...(initialTab ? { initialTab } : {})} />;
}
