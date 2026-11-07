import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { publicCareersClient } from "@/components/careers/public-client";
import { formatUk } from "@/lib/ui/dates";

export const metadata: Metadata = { title: "Careers" };

export default async function Page({ params }: { params: Promise<{ company: string }> }) {
  const { company } = await params;
  const { data } = await publicCareersClient().GET("/public/careers/{company_slug}", {
    params: { path: { company_slug: company } },
  });
  if (!data) notFound();
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-large-title text-label">{data.company} careers</h1>
        <p className="text-callout text-label-secondary">Open roles at {data.company}.</p>
      </header>
      {data.postings.length === 0 ? (
        <p className="text-callout text-label-secondary">There are no open roles right now.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {data.postings.map((posting) => (
            <li key={posting.slug}>
              <Link
                href={`/careers/${company}/${posting.slug}`}
                className="border-separator flex flex-col gap-1 rounded-xl border p-4 hover:bg-fill-secondary"
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
    </main>
  );
}
