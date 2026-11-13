import { Attribution } from "@/components/register/attribution";
import { Section, SectionHeading } from "@/components/marketing/sections";
import { ReportForm } from "@/components/register/report-form";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata(
  "/sponsors/methodology",
  "How the sponsor register pages are built",
  "Where the data comes from, how often it is checked and how the changes are worked out.",
);

export default function Page() {
  return (
    <Section tone="page">
      <SectionHeading level={1} eyebrow="Sponsor register" title="Methodology" />
      <div className="text-lead text-label mx-auto mt-8 flex max-w-3xl flex-col gap-4">
        <p>
          The data is the register of licensed sponsors that the Home Office publishes on GOV.UK. We
          check for a new publication on working days, and keep every version we see.
        </p>
        <p>
          Each publication is compared with the one before it. A sponsor that appears for the first
          time is added; one that is missing is no longer listed; one that reappears has returned.
          Changes of route or rating are recorded too.
        </p>
        <p>
          A new and a removed sponsor in the same town with a very similar name may be the same
          organisation under a new name. We say so as a possibility and never merge them.
        </p>
        <p>
          Towns are placed in a region from the ONS Index of Place Names. Where the town is
          ambiguous or unknown, the sponsor has no region. Industry comes from Companies House where
          we can match the name with confidence.
        </p>
        <h2 className="text-title-3 font-semibold">Report a problem with an entry</h2>
        <ReportForm />
        <Attribution />
      </div>
    </Section>
  );
}
