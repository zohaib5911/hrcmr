import { ResourceCards, ResourceHub } from "@/components/resources/hub";
import { resourceCategories } from "@/lib/resources";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata(
  "/resources",
  "Employer resources",
  "Guides, free tools and templates for UK employers and sponsors.",
);
export default function ResourcesPage() {
  return (
    <ResourceHub
      title="Employer resources"
      description="Find practical guides, free tools and templates for looking after your people and managing sponsor duties."
    >
      <ResourceCards items={resourceCategories} />
    </ResourceHub>
  );
}
