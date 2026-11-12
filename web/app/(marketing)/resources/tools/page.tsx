import { ResourceCards, ResourceHub } from "@/components/resources/hub";
import { resourceTools } from "@/lib/resources";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata(
  "/resources/tools",
  "Free employer tools",
  "Free calculators and checkers for UK pay, leave, Right to Work and sponsorship planning.",
);
export default function ToolsPage() {
  return (
    <ResourceHub
      title="Free employer tools"
      description="Choose a calculator, checker or document builder. Each tool explains its inputs, assumptions and sources; check the result against your circumstances."
    >
      <ResourceCards
        items={resourceTools.map((tool) => ({ ...tool, href: `/resources/tools/${tool.slug}` }))}
      />
    </ResourceHub>
  );
}
