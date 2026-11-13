import {
  PublicBody,
  PublicContentFrame,
  PublicDate,
  PublicLead,
} from "@/components/marketing/public-content";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { Breadcrumbs } from "@/components/app/breadcrumbs";
import { Faq } from "@/components/marketing/faq";
import { CtaBand } from "@/components/marketing/sections";
import { StatusChip } from "@/components/ui/status-chip";
import {
  privacyNotices,
  relatedTools,
  type CalculatorFrameContent,
  type CalculatorPrivacyMode,
  type ResourceToolSlug,
} from "@/lib/calculators/frame";
import { SIGN_UP } from "@/lib/marketing-nav";

export type CalculatorSource = {
  title: string;
  url: string;
  checkedOn: string;
  validFrom: string;
  validTo: string | null;
};

/**
 * Shared public-tool frame (plan L1479): breadcrumb, free-tool badge, quick answer, the tool,
 * how it works, sources, FAQ, disclaimer, CTA and more tools. The calculator owns its local
 * input/result state (and its own preset chips and steps).
 */
export function CalculatorTemplate({
  title,
  description,
  sources,
  children,
  slug,
  privacy = "memory",
  content = {},
}: {
  title: string;
  description: string;
  sources: readonly CalculatorSource[];
  children: ReactNode;
  /** The tool's `resourceTools` slug; it is left out of "More tools". */
  slug?: ResourceToolSlug;
  privacy?: CalculatorPrivacyMode;
  content?: CalculatorFrameContent;
}) {
  const { quickAnswer, howItWorks = [], faq = [] } = content;
  const more = relatedTools(slug);
  return (
    <>
      <PublicContentFrame>
        <header className="pb-8">
          <Breadcrumbs
            crumbs={[
              { label: "Resources", href: "/resources" },
              { label: "Tools", href: "/resources/tools" },
              { label: title },
            ]}
          />
          <StatusChip tone="info" className="mt-4">
            Free tool
          </StatusChip>
          <h1 className="text-large-title text-label mt-3">{title}</h1>
          <PublicLead className="mt-3">{description}</PublicLead>
          <p className="text-footnote text-label-secondary mt-3">
            {privacyNotices[privacy]} General guidance only; this tool does not provide legal or
            immigration advice.
          </p>
        </header>
        {quickAnswer ? (
          <section
            aria-labelledby="calculator-quick-answer"
            className="bg-elevated rounded-control mb-8 p-5"
          >
            <h2 id="calculator-quick-answer" className="text-headline text-label">
              Quick answer
            </h2>
            <PublicBody className="text-label mt-2">{quickAnswer}</PublicBody>
          </section>
        ) : null}
        {children}
        {howItWorks.length > 0 ? (
          <section aria-labelledby="calculator-how" className="mt-10">
            <h2 id="calculator-how" className="text-title-2 text-label">
              How it works
            </h2>
            <ol className="mt-4 space-y-4">
              {howItWorks.map((step, index) => (
                <li key={step.title} className="flex gap-4">
                  <span
                    aria-hidden="true"
                    className="bg-accent-tint text-accent-text text-headline flex size-8 shrink-0 items-center justify-center rounded-full"
                  >
                    {index + 1}
                  </span>
                  <div>
                    <h3 className="text-headline text-label">{step.title}</h3>
                    <PublicBody className="mt-1">{step.body}</PublicBody>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        ) : null}
        <section aria-labelledby="calculator-sources" className="mt-10">
          <h2 id="calculator-sources" className="text-title-2 text-label">
            Sources and dates
          </h2>
          <div className="mt-4 overflow-x-auto">
            <table className="text-footnote text-label w-full text-left">
              <caption className="sr-only">Official sources used by this tool</caption>
              <thead className="text-label-secondary">
                <tr>
                  <th scope="col" className="p-3">
                    Source
                  </th>
                  <th scope="col" className="p-3">
                    Checked on
                  </th>
                  <th scope="col" className="p-3">
                    Applies from
                  </th>
                  <th scope="col" className="p-3">
                    Applies until
                  </th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <tr key={source.url} className="border-separator border-t">
                    <th scope="row" className="p-3 font-normal">
                      <a href={source.url} className="text-accent-text underline">
                        {source.title}
                      </a>
                    </th>
                    <td className="p-3 whitespace-nowrap">
                      <PublicDate value={source.checkedOn} />
                    </td>
                    <td className="p-3 whitespace-nowrap">
                      <PublicDate value={source.validFrom} />
                    </td>
                    <td className="p-3">
                      {source.validTo ? (
                        <PublicDate value={source.validTo} />
                      ) : (
                        "No end date specified"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-footnote text-label-secondary mt-3">
            Rules can change. Review the linked guidance before acting on a result.
          </p>
        </section>
        {faq.length > 0 ? (
          <section aria-labelledby="calculator-faq" className="mt-10">
            <h2 id="calculator-faq" className="text-title-2 text-label mb-4">
              Questions
            </h2>
            <Faq items={faq} />
          </section>
        ) : null}
        {more.length > 0 ? (
          <nav aria-labelledby="calculator-more" className="mt-10">
            <h2 id="calculator-more" className="text-title-2 text-label">
              More tools
            </h2>
            <ul className="mt-4 grid gap-3 sm:grid-cols-3">
              {more.map((tool) => (
                <li key={tool.slug}>
                  <Link
                    href={`/resources/tools/${tool.slug}` as Route}
                    prefetch={false}
                    className="bg-elevated rounded-control block h-full p-4 hover:underline"
                  >
                    <span className="text-headline text-accent-text">{tool.title}</span>
                    <span className="text-footnote text-label-secondary mt-1 block">
                      {tool.description}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ) : null}
      </PublicContentFrame>
      <CtaBand
        title="Keep sponsor and HR records in one place"
        lead="Start on the free plan. No card needed."
        actions={[{ label: SIGN_UP.label, href: SIGN_UP.href }]}
      />
    </>
  );
}
