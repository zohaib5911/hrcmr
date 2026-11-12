import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { PublicSalaryChecker } from "@/components/soc/public-checker";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/sponsorship-job-checker",
  "Sponsorship job checker",
  "Find the SOC 2020 occupation code for a job and see the Skilled Worker salary table. General guidance, not legal or immigration advice.",
);

export default function Page() {
  return (
    <div className="mx-auto max-w-5xl px-5 py-10 sm:px-8 sm:py-14">
      <header className="pb-8">
        <h1 className="text-large-title text-label">Sponsorship job checker</h1>
        <p className="text-callout text-label-secondary mt-2 max-w-2xl">
          Find the occupation code for a job and see the minimum salary for the Skilled Worker
          route. General guidance, not legal or immigration advice.
        </p>
      </header>
      <PublicSalaryChecker />
    </div>
  );
}
