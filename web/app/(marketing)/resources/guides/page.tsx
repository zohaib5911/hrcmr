import { formatUk } from "@/lib/ui/dates";
import { ResourceCards, ResourceHub } from "@/components/resources/hub";
import { guides } from "@/lib/guides/catalogue";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata(
  "/resources/guides",
  "Employer guides",
  "Practical guides to Right to Work checks, sponsor duties and statutory holiday entitlement.",
);
export default function GuidesPage() {
  return (
    <ResourceHub
      title="Employer guides"
      description="Read practical guidance with official sources, review dates and next steps. Try the 26-question sponsor audit preparation self-test."
    >
      <ResourceCards
        items={guides.map((guide) => ({
          ...guide,
          href: `/resources/guides/${guide.slug}`,
          detail: `Last reviewed: ${formatUk(guide.reviewedOn)}`,
        }))}
      />
    </ResourceHub>
  );
}
