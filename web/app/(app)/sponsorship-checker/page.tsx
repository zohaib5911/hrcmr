import type { Metadata } from "next";

import { SponsorshipChecker } from "@/components/soc/checker";

export const metadata: Metadata = { title: "Sponsorship checker" };

export default function Page() {
  return <SponsorshipChecker />;
}
