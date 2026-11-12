import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { brand } from "@brand";

import { CtaBand, Section, SectionHeading } from "@/components/marketing/sections";
import { SIGN_UP } from "@/lib/marketing-nav";

export const metadata: Metadata = pageMetadata(
  "/sponsor-licence-compliance/reporting-duties",
  "Sponsor reporting duties",
  `The changes a sponsor must report and how ${brand.name} tracks the deadlines.`,
);

const WORKER_CHANGES = [
  "A worker does not start work.",
  "A worker is absent without permission for more than 10 working days.",
  "A worker leaves, or sponsorship stops, including by dismissal or resignation.",
  "A worker's salary is reduced.",
  "A worker's job or occupation code changes.",
  "A worker's main work location changes.",
  "A worker's working hours change.",
  "A worker has unpaid or reduced-pay absence of more than four weeks in a year.",
] as const;

export default function ReportingDutiesPage() {
  return (
    <>
      <Section tone="page" className="pb-8 md:pb-12">
        <SectionHeading
          level={1}
          eyebrow="Sponsor compliance"
          title="Reporting duties"
          lead="A summary of the changes a licence holder is expected to report, and the time allowed."
        />
      </Section>
      <Section tone="raised">
        <div className="text-body text-label mx-auto flex max-w-[45rem] flex-col gap-5">
          <h2 className="text-title-3 font-semibold">Changes to a worker: 10 working days</h2>
          <p className="text-label-secondary">
            These are counted in working days from the date of the change, leaving out weekends and
            bank holidays in the nation where the person works.
          </p>
          <ul className="text-label-secondary list-disc pl-6">
            {WORKER_CHANGES.map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
          <h2 className="text-title-3 font-semibold">
            Changes to your organisation: 20 working days
          </h2>
          <p className="text-label-secondary">
            Changes to the organisation itself, such as a new authorising officer, key contact or
            level 1 user, a change of address or a change of legal structure, have a longer limit.
          </p>
          <h2 className="text-title-3 font-semibold">How {brand.name} helps</h2>
          <p className="text-label-secondary">
            Record the change and its date and the deadline is worked out for you and added to your
            dashboard. Once you have reported, note the date and reference so the proof stays with
            the record.
          </p>
          <p className="text-footnote text-label-secondary border-separator border-t pt-5">
            This is general information, not legal or immigration advice. The rules change; check
            the current Home Office guidance for sponsors before you rely on a date.
          </p>
        </div>
      </Section>
      <CtaBand
        title="Let the dates come to you"
        actions={[{ label: SIGN_UP.label, href: SIGN_UP.href }]}
      />
    </>
  );
}
