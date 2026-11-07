import type { Metadata } from "next";

import { CandidateProfile } from "@/components/recruitment/candidate-profile";

export const metadata: Metadata = { title: "Candidate" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CandidateProfile candidateId={id} />;
}
