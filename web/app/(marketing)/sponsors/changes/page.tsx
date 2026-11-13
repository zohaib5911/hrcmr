import Link from "next/link";

import { Attribution } from "@/components/register/attribution";
import { Section, SectionHeading } from "@/components/marketing/sections";
import { type BulletinList, registerGet } from "@/lib/register";
import { pageMetadata } from "@/lib/seo";
import { formatUk } from "@/lib/ui/dates";

export const dynamic = "force-dynamic";
export const metadata = pageMetadata(
  "/sponsors/changes",
  "Sponsor register change bulletins",
  "Each publication of the UK register of licensed sponsors: who was added, who is no longer listed.",
);

export default async function Page() {
  const data = await registerGet<BulletinList>("/changes", 600);
  return (
    <Section tone="page">
      <SectionHeading
        level={1}
        eyebrow="Sponsor register"
        title="Change bulletins"
        lead="What changed in each publication of the register."
      />
      <div className="mx-auto mt-10 max-w-3xl overflow-x-auto">
        {!data || data.bulletins.length === 0 ? (
          <p className="text-lead text-label-secondary">No publications have been recorded yet.</p>
        ) : (
          <table className="text-body w-full text-left">
            <caption className="sr-only">Changes by publication date</caption>
            <thead className="text-footnote text-label-secondary">
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Added</th>
                <th scope="col">No longer listed</th>
                <th scope="col">Returned</th>
                <th scope="col">Net</th>
              </tr>
            </thead>
            <tbody>
              {data.bulletins.map((b) => (
                <tr key={b.date}>
                  <th scope="row" className="font-normal">
                    <Link
                      href={`/sponsors/changes/${b.date}`}
                      className="inline-flex min-h-11 items-center underline"
                    >
                      {formatUk(b.date)}
                    </Link>
                  </th>
                  <td>{b.added}</td>
                  <td>{b.removed}</td>
                  <td>{b.returned}</td>
                  <td>{b.net > 0 ? `+${b.net}` : b.net}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div className="mx-auto max-w-3xl">
        <Attribution />
      </div>
    </Section>
  );
}
