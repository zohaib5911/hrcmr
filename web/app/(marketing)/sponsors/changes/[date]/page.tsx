import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Attribution } from "@/components/register/attribution";
import { Section, SectionHeading } from "@/components/marketing/sections";
import { type Bulletin, registerGet } from "@/lib/register";
import { pageMetadata } from "@/lib/seo";
import { formatUk } from "@/lib/ui/dates";

export const revalidate = 3600;

type Props = { params: Promise<{ date: string }> };
type Item = Bulletin["added_list"][number];

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { date } = await params;
  return pageMetadata(
    `/sponsors/changes/${date}`,
    `Sponsor register changes, ${/^\d{4}-\d{2}-\d{2}$/.test(date) ? formatUk(date) : "bulletin"}`,
    "Organisations added to and no longer listed on the UK register of licensed sponsors.",
  );
}

function List({ title, items }: { title: string; items: Item[] }) {
  if (items.length === 0) return null;
  return (
    <section aria-label={title} className="mt-8">
      <h2 className="text-title-3 text-label font-semibold">{title}</h2>
      <ul className="text-body mt-3 flex flex-col gap-1">
        {items.map((s) => (
          <li key={s.stable_id}>
            <Link href={`/sponsors/profile/${s.stable_id}/${s.slug}`} className="underline">
              {s.name}
            </Link>{" "}
            <span className="text-label-secondary">{s.town}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default async function Page({ params }: Props) {
  const { date } = await params;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) notFound();
  const data = await registerGet<Bulletin>(`/changes/${date}`);
  if (!data) notFound();
  return (
    <Section tone="page">
      <SectionHeading
        level={1}
        eyebrow="Change bulletin"
        title={`Register changes, ${formatUk(data.date)}`}
      />
      <dl className="mx-auto mt-8 grid max-w-3xl grid-cols-2 gap-4 md:grid-cols-4">
        {(
          [
            ["Added", data.added],
            ["No longer listed", data.removed],
            ["Returned", data.returned],
            ["Net change", data.net > 0 ? `+${data.net}` : data.net],
          ] as const
        ).map(([label, value]) => (
          <div key={label}>
            <dt className="text-footnote text-label-secondary">{label}</dt>
            <dd className="text-title-2 text-label">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="mx-auto max-w-3xl">
        {data.median_added_last_28 !== null && (
          <p className="text-lead text-label-secondary mt-4">
            The median number added in the previous 28 publications was {data.median_added_last_28}.
          </p>
        )}
        {data.regions.length > 0 && (
          <section aria-label="Where the changes were" className="mt-8">
            <h2 className="text-title-3 text-label font-semibold">Where the changes were</h2>
            <ul className="text-body mt-3 flex flex-col gap-1">
              {data.regions.map((r) => (
                <li key={r.town}>
                  {r.town} <span className="text-label-secondary">({r.count})</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        {data.possibly_same.length > 0 && (
          <section aria-label="Possibly the same sponsor" className="mt-8">
            <h2 className="text-title-3 text-label font-semibold">Possibly the same sponsor</h2>
            <ul className="text-body mt-3 flex flex-col gap-1">
              {data.possibly_same.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        )}
        <List title="Added" items={data.added_list} />
        <List title="No longer listed" items={data.removed_list} />
        <List title="Returned" items={data.returned_list} />
        {data.truncated && (
          <p className="text-footnote text-label-secondary mt-4">
            Long lists are cut short. The counts above are complete.
          </p>
        )}
        <Attribution />
      </div>
    </Section>
  );
}
