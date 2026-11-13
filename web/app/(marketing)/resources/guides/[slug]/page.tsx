import { PublicContentFrame, PublicDate, PublicLead } from "@/components/marketing/public-content";
import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ComponentType } from "react";

import FollowUp from "../../../../../../content/guides/follow-up-right-to-work-checks.mdx";
import OctoberChanges from "../../../../../../content/guides/right-to-work-changes-october-2026.mdx";
import RightToWork from "../../../../../../content/guides/right-to-work-checks.mdx";
import AuditPreparation from "../../../../../../content/guides/sponsor-licence-audit-preparation.mdx";
import Reporting from "../../../../../../content/guides/sponsor-reporting-duties.mdx";
import Holiday from "../../../../../../content/guides/statutory-holiday-entitlement.mdx";

import { AuditSelfTest } from "@/components/guides/audit-self-test";
import { findGuide, guideDisclaimer, guides, type GuideSlug } from "@/lib/guides/catalogue";

const content: Record<GuideSlug, ComponentType> = {
  "right-to-work-checks": RightToWork,
  "follow-up-right-to-work-checks": FollowUp,
  "right-to-work-changes-october-2026": OctoberChanges,
  "sponsor-licence-audit-preparation": AuditPreparation,
  "statutory-holiday-entitlement": Holiday,
  "sponsor-reporting-duties": Reporting,
};

export const dynamicParams = false;

export function generateStaticParams() {
  return guides.map(({ slug }) => ({ slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const guide = findGuide((await params).slug);
  if (!guide) notFound();
  return pageMetadata(`/resources/guides/${guide.slug}`, guide.title, guide.description);
}

export default async function GuidePage({ params }: Props) {
  const guide = findGuide((await params).slug);
  if (!guide) notFound();
  const Content = content[guide.slug];
  return (
    <PublicContentFrame>
      <article className="mx-auto max-w-[45rem]">
        <header>
          <h1 className="text-large-title text-label">{guide.title}</h1>
          <PublicLead className="mt-3">{guide.description}</PublicLead>
          <p className="text-caption text-label-secondary mt-3">
            Last reviewed: <PublicDate value={guide.reviewedOn} />
          </p>
        </header>
        <aside
          aria-label="Resources disclaimer"
          className="bg-elevated text-callout text-label-secondary rounded-card my-6 p-4"
        >
          {guideDisclaimer}
        </aside>
        <Content />
        {guide.slug === "sponsor-licence-audit-preparation" ? <AuditSelfTest /> : null}
        <section aria-labelledby="guide-sources" className="border-separator mt-10 border-t pt-6">
          <h2 id="guide-sources" className="text-title-2 text-label">
            Sources
          </h2>
          <p className="text-callout text-label-secondary mt-2">
            Official sources checked on <PublicDate value={guide.reviewedOn} />. Check for updates
            before acting.
          </p>
          <ul className="mt-3 list-disc space-y-3 pl-5">
            {guide.sources.map((source) => (
              <li key={source.url}>
                <a
                  className="text-accent-text break-words underline underline-offset-4"
                  href={source.url}
                >
                  {source.title}
                </a>
              </li>
            ))}
          </ul>
        </section>
      </article>
    </PublicContentFrame>
  );
}
