import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import Link from "next/link";

import { brand } from "@brand";

import { publicCareersClient } from "@/components/careers/public-client";
import { Section, SectionHeading } from "@/components/marketing/sections";
import { formatUk } from "@/lib/ui/dates";

export const metadata: Metadata = pageMetadata(
  "/careers",
  "Careers",
  `Open roles at ${brand.name}.`,
);

// Read at request time: the slug of our own company in the product, so its careers come from the module.
export const dynamic = "force-dynamic";

export default async function CareersPage() {
  const slug = process.env.OWN_COMPANY_SLUG;
  const page = slug
    ? (
        await publicCareersClient()
          .GET("/public/careers/{company_slug}", {
            params: { path: { company_slug: slug } },
          })
          .catch(() => ({ data: undefined }))
      ).data
    : undefined;
  return (
    <Section tone="raised">
      <SectionHeading
        level={1}
        title={`Work at ${brand.name}`}
        lead="Open roles in our own team."
        className="mb-10"
      />
      <div className="mx-auto max-w-[45rem]">
        {!page || page.postings.length === 0 ? (
          <p className="text-body text-label-secondary text-center">
            There are no open roles right now. Please look again soon.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {page.postings.map((posting) => (
              <li key={posting.slug}>
                <Link
                  href={`/careers/${slug}/${posting.slug}` as never}
                  className="border-separator hover:bg-fill-secondary flex flex-col gap-1 rounded-xl border p-4"
                >
                  <span className="text-headline text-label">{posting.title}</span>
                  <span className="text-footnote text-label-secondary">
                    {[
                      posting.location,
                      posting.closes_on ? `closes ${formatUk(posting.closes_on)}` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Section>
  );
}
