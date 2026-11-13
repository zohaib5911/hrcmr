import { PublicBody } from "@/components/marketing/public-content";
import Link from "next/link";
import type { Route } from "next";
import type { ReactNode } from "react";
import { Section, SectionHeading } from "@/components/marketing/sections";
import { resourceCategories } from "@/lib/resources";

export function ResourceHub({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <>
      <Section>
        <SectionHeading level={1} title={title} lead={description} eyebrow="Employer resources" />
        <nav aria-label="Resource categories" className="mt-8 flex flex-wrap justify-center gap-5">
          <Link className="text-accent-text underline underline-offset-4" href="/resources">
            All resources
          </Link>
          {resourceCategories.map(({ href, title }) => (
            <Link key={href} className="text-accent-text underline underline-offset-4" href={href}>
              {title}
            </Link>
          ))}
        </nav>
      </Section>
      <Section tone="page" label={title}>
        {children}
      </Section>
      <Section label="Using these resources">
        <PublicBody className="mx-auto">
          General information only. Check the sources and dates in each resource before acting.
          These resources do not replace legal, immigration or employment advice. Read our{" "}
          <Link
            className="text-accent-text underline underline-offset-4"
            href="/legal/resources-disclaimer"
          >
            resources disclaimer
          </Link>
          .
        </PublicBody>
      </Section>
    </>
  );
}

export function ResourceCards({
  items,
}: {
  items: readonly { href: string; title: string; description: string; detail?: string }[];
}) {
  return (
    <ul className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {items.map(({ href, title, description, detail }) => (
        <li key={href} className="rounded-card border-separator bg-elevated border p-6">
          <h3 className="text-title-3 text-label">
            <Link
              className="hover:text-accent-text underline underline-offset-4"
              href={href as Route}
            >
              {title}
            </Link>
          </h3>
          <PublicBody className="mt-3">{description}</PublicBody>
          {detail ? <p className="text-footnote text-label-secondary mt-3">{detail}</p> : null}
        </li>
      ))}
    </ul>
  );
}
