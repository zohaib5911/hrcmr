import { ResourceHub } from "@/components/resources/hub";
import { isPublishable, loadTemplates } from "@/lib/templates/manifest";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata(
  "/resources/templates",
  "Employer templates",
  "Original employment documents and checklists, available after human review.",
);
export default function TemplatesPage() {
  const templates = loadTemplates().filter(isPublishable);
  return (
    <ResourceHub
      title="Employer templates"
      description="Original employment documents and checklists to adapt to your organisation. Every template needs human review before publication."
    >
      {templates.length === 0 ? (
        <p className="text-body text-label-secondary mx-auto max-w-3xl text-center">
          Our templates are awaiting human review. Downloads will appear here once reviewed. In the
          meantime, explore our guides and free tools.
        </p>
      ) : (
        <ul className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <li
              key={template.slug}
              className="rounded-card border-separator bg-elevated border p-6"
            >
              <h3 className="text-title-3 text-label">{template.title}</h3>
              <p className="text-body text-label-secondary mt-3">{template.description}</p>
              <p className="text-footnote text-label-secondary mt-3">
                Version {template.version} · Reviewed: {template.reviewed_on}
              </p>
              <a
                className="text-accent-text mt-4 inline-block underline underline-offset-4"
                href={`/resources/templates/download/${template.file}`}
                download
              >
                Download {template.title} ({template.file.endsWith(".pdf") ? "PDF" : "DOCX"})
              </a>
            </li>
          ))}
        </ul>
      )}
    </ResourceHub>
  );
}
