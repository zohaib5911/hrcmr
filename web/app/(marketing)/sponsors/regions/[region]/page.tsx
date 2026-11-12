import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Attribution } from "@/components/register/attribution";
import { Section, SectionHeading } from "@/components/marketing/sections";
import { type Region, registerGet, slugify } from "@/lib/register";
import { pageMetadata } from "@/lib/seo";
import { formatUk } from "@/lib/ui/dates";

export const revalidate = 3600;
export const generateStaticParams = () => [];

type Props = { params: Promise<{ region: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { region } = await params;
  const data = await registerGet<Region>(`/regions/${encodeURIComponent(region)}`);
  if (!data) return { title: "Region not found", robots: { index: false } };
  return pageMetadata(
    `/sponsors/regions/${data.slug}`,
    `Licensed sponsors in ${data.region}`,
    `${data.sponsors} organisations on the UK register of licensed sponsors are in ${data.region}.`,
  );
}

export default async function Page({ params }: Props) {
  const { region } = await params;
  const data = await registerGet<Region>(`/regions/${encodeURIComponent(region)}`);
  if (!data) notFound();
  return (
    <Section tone="page">
      <SectionHeading
        level={1}
        eyebrow="Sponsor register"
        title={`Licensed sponsors in ${data.region}`}
        lead={`${data.sponsors.toLocaleString("en-GB")} organisations currently listed${
          data.last_published ? `, register published ${formatUk(data.last_published)}` : ""
        }.`}
      />
      <div className="mx-auto mt-10 grid max-w-3xl gap-8 md:grid-cols-2">
        <section aria-labelledby="towns">
          <h2 id="towns" className="text-title-3 text-label font-semibold">
            Sponsors by town
          </h2>
          <ul className="text-body mt-3 flex flex-col gap-1">
            {data.towns.map((t) => (
              <li key={t.town}>
                {t.town} <span className="text-label-secondary">({t.count})</span>
              </li>
            ))}
          </ul>
        </section>
        <section aria-labelledby="routes">
          <h2 id="routes" className="text-title-3 text-label font-semibold">
            Routes
          </h2>
          <ul className="text-body mt-3 flex flex-col gap-1">
            {data.routes.map((r) => (
              <li key={r.town}>
                {r.town} <span className="text-label-secondary">({r.count})</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <section aria-labelledby="latest" className="mx-auto mt-10 max-w-3xl">
        <h2 id="latest" className="text-title-3 text-label font-semibold">
          Latest changes here
        </h2>
        {data.latest_changes.length === 0 ? (
          <p className="text-body text-label-secondary mt-3">
            No changes in the latest publication.
          </p>
        ) : (
          <ul className="text-body mt-3 flex flex-col gap-1">
            {data.latest_changes.map((c) => (
              <li key={`${c.stable_id}-${c.change}`}>
                <Link
                  href={`/sponsors/profile/${c.stable_id}/${slugify(c.name)}`}
                  className="underline"
                >
                  {c.name}
                </Link>{" "}
                <span className="text-label-secondary">
                  {c.town}, {c.change}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <div className="mx-auto max-w-3xl">
        <Attribution />
      </div>
    </Section>
  );
}
