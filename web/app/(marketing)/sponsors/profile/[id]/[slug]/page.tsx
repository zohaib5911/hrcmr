import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Attribution } from "@/components/register/attribution";
import { ReportForm } from "@/components/register/report-form";
import { Section, SectionHeading } from "@/components/marketing/sections";
import { CHANGE_LABELS, type Profile, registerGet } from "@/lib/register";
import { pageMetadata } from "@/lib/seo";
import { formatUk } from "@/lib/ui/dates";

// Render with a fresh CSP nonce; registerGet caches public profile data for six hours.
export const revalidate = 21600;

type Props = { params: Promise<{ id: string; slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const data = await registerGet<Profile>(`/sponsors/${id}`, 21600);
  if (!data) return { title: "Sponsor not found", robots: { index: false } };
  return pageMetadata(
    `/sponsors/profile/${data.stable_id}/${data.slug}`,
    `${data.name} on the sponsor register`,
    `${data.name}, ${data.town}: routes, ratings and changes on the UK register of licensed sponsors.`,
  );
}

export default async function Page({ params }: Props) {
  const { id } = await params;
  const data = await registerGet<Profile>(`/sponsors/${id}`, 21600);
  if (!data) notFound();
  return (
    <Section tone="page">
      <nav aria-label="Breadcrumb" className="text-footnote text-label-secondary mb-4">
        <Link href="/sponsors" className="underline">
          Sponsor register
        </Link>
        {data.region && data.region_slug ? (
          <>
            {" / "}
            <Link href={`/sponsors/regions/${data.region_slug}`} className="underline">
              {data.region}
            </Link>
          </>
        ) : null}
      </nav>
      <SectionHeading
        level={1}
        eyebrow={data.current ? "Currently on the register" : "No longer listed"}
        title={data.name}
        lead={[data.town, data.county].filter(Boolean).join(", ")}
      />
      <div className="mx-auto mt-10 max-w-3xl">
        <section aria-labelledby="entry">
          <h2 id="entry" className="text-title-3 text-label font-semibold">
            Current entry
          </h2>
          {data.entries.length === 0 ? (
            <p className="text-lead text-label-secondary mt-3">
              No entry in the latest publication.
            </p>
          ) : (
            <table className="text-body mt-3 w-full text-left">
              <thead className="text-footnote text-label-secondary">
                <tr>
                  <th scope="col">Route</th>
                  <th scope="col">Licence type and rating</th>
                </tr>
              </thead>
              <tbody>
                {data.entries.map((e) => (
                  <tr key={`${e.route}-${e.type_rating}`}>
                    <td>{e.route}</td>
                    <td>{e.type_rating}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
        <section aria-labelledby="lifeline" className="mt-8">
          <h2 id="lifeline" className="text-title-3 text-label font-semibold">
            Licence lifeline
          </h2>
          <p className="text-lead mt-3">
            First seen {formatUk(data.first_seen_on)}. Last seen {formatUk(data.last_seen_on)}.
          </p>
          {data.changes.length > 0 && (
            <ul className="text-body mt-3 flex flex-col gap-1">
              {data.changes.map((c, i) => (
                <li key={`${c.date}-${c.change}-${i}`}>
                  <time dateTime={c.date}>{formatUk(c.date)}</time>:{" "}
                  {CHANGE_LABELS[c.change] ?? c.change}
                </li>
              ))}
            </ul>
          )}
        </section>
        <section aria-labelledby="report" className="mt-10">
          <h2 id="report" className="text-title-3 text-label font-semibold">
            Report a problem with this entry
          </h2>
          <div className="mt-3">
            <ReportForm sponsorId={data.stable_id} />
          </div>
        </section>
        <Attribution />
      </div>
    </Section>
  );
}
