import { pageMetadata } from "@/lib/seo";
import type { Metadata, Route } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { brand } from "@brand";
import { CookieSettingsButton } from "@/components/marketing/cookie-consent";
import { LEGAL_DOCUMENTS, LEGAL_DRAFT_DATE, LEGAL_DRAFT_NOTICE, legalDocument } from "@/lib/legal";

type Props = { params: Promise<{ document: string }> };

export function generateStaticParams() {
  return LEGAL_DOCUMENTS.map(({ slug }) => ({ document: slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const document = legalDocument((await params).document);
  return {
    ...pageMetadata(
      `/legal/${document?.slug ?? ""}`,
      document?.title ?? "Legal document",
      document?.introduction ?? "Legal document draft.",
    ),
    robots: { index: false },
  };
}

export default async function LegalPage({ params }: Props) {
  const document = legalDocument((await params).document);
  if (!document) notFound();
  return (
    <article className="page-marketing py-16 md:py-24">
      <div className="mx-auto max-w-3xl">
        <p className="text-warning text-headline mb-4" role="note">
          {LEGAL_DRAFT_NOTICE}
        </p>
        <h1 className="text-large-title text-label font-semibold">{document.title}</h1>
        <p className="text-footnote text-label-secondary mt-3">
          Draft prepared {LEGAL_DRAFT_DATE}. Not yet approved for launch.
        </p>
        <p className="text-body text-label-secondary mt-6">{document.introduction}</p>
        <p className="text-callout text-label-secondary mt-4">
          Provider:{" "}
          {brand.legal.companyName ?? "legal company identity awaiting owner confirmation"}.
          {brand.legal.registeredOffice
            ? ` Registered office: ${brand.legal.registeredOffice}.`
            : " Registered office awaiting confirmation."}
        </p>
        <nav
          aria-label="Legal documents"
          className="border-separator my-8 flex flex-wrap gap-x-5 gap-y-3 border-y py-5"
        >
          {LEGAL_DOCUMENTS.map(({ slug, title }) => (
            <Link
              key={slug}
              href={`/legal/${slug}` as Route}
              aria-current={slug === document.slug ? "page" : undefined}
              className="text-link text-callout underline"
              prefetch={false}
            >
              {title}
            </Link>
          ))}
          <Link
            href={"/accessibility" as Route}
            className="text-link text-callout underline"
            prefetch={false}
          >
            Accessibility
          </Link>
        </nav>
        {document.sections.map((section) => (
          <section key={section.title} className="mt-8">
            <h2 className="text-title-3 text-label font-semibold">{section.title}</h2>
            {section.paragraphs.map((paragraph) => (
              <p key={paragraph} className="text-body text-label-secondary mt-3">
                {paragraph}
              </p>
            ))}
          </section>
        ))}
        {document.slug === "cookies" && (
          <CookieSettingsButton className="text-link mt-8 underline" />
        )}
        <p className="text-callout text-label-secondary mt-10">
          Questions or requests:{" "}
          <Link href={"/contact" as Route} className="text-link underline" prefetch={false}>
            contact us
          </Link>
          .
        </p>
        {(document.slug === "privacy" ||
          document.slug === "dpa" ||
          document.slug === "cookies") && (
          <p className="text-footnote text-label-secondary mt-4">
            Drafting references:{" "}
            <a
              className="text-link underline"
              href="https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/guide-to-accountability-and-governance/contracts/"
            >
              ICO processor contracts
            </a>{" "}
            and{" "}
            <a
              className="text-link underline"
              href="https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/cookies-and-similar-technologies/"
            >
              ICO cookies guidance
            </a>
            . Checked {LEGAL_DRAFT_DATE}.
          </p>
        )}
        {document.slug === "register-terms" && (
          <p className="text-footnote text-label-secondary mt-4">
            Contains public sector information licensed under the{" "}
            <a
              className="text-link underline"
              href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
            >
              Open Government Licence v3.0
            </a>
            . We are independent of the Home Office. A licence does not mean an employer is hiring.{" "}
            <a
              className="text-link underline"
              href="https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
            >
              Official register
            </a>
            .
          </p>
        )}
      </div>
    </article>
  );
}
