import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ApplyForm } from "@/components/careers/apply-form";
import { CareersLogo } from "@/components/careers/careers-logo";
import { publicCareersClient } from "@/components/careers/public-client";
import { formatUk } from "@/lib/ui/dates";

export const metadata: Metadata = { title: "Apply" };

const VISA: Record<string, string> = {
  not_stated: "Visa sponsorship: not stated.",
  available: "Visa sponsorship is available.",
  considered: "Visa sponsorship is considered for the right candidate.",
  not_available: "Visa sponsorship is not available.",
};

export default async function Page({
  params,
}: {
  params: Promise<{ company: string; posting: string }>;
}) {
  const { company, posting } = await params;
  const { data } = await publicCareersClient().GET(
    "/public/postings/{company_slug}/{posting_slug}",
    {
      params: { path: { company_slug: company, posting_slug: posting } },
    },
  );
  if (!data) notFound();
  const pay =
    data.salary_from || data.salary_to
      ? `${data.salary_from ?? ""}${data.salary_from && data.salary_to ? " to " : ""}${data.salary_to ?? ""}${data.salary_per ? ` per ${data.salary_per}` : ""}`
      : null;
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10">
      <header className="flex flex-col gap-2">
        <CareersLogo company={company} name={data.company} hasLogo={data.has_logo} />
        <p className="text-callout text-label-secondary">{data.company}</p>
        <h1 className="text-large-title text-label break-words">{data.title}</h1>
        <p className="text-callout text-label-secondary">
          {[data.location, data.weekly_hours ? `${data.weekly_hours} hours a week` : null, pay]
            .filter(Boolean)
            .join(" · ")}
        </p>
        {data.closes_on && <p className="text-callout">Closes {formatUk(data.closes_on)}</p>}
        <p className="text-callout">{VISA[data.visa_sponsorship]}</p>
      </header>
      {data.description && (
        <section className="text-body whitespace-pre-line">{data.description}</section>
      )}
      <ApplyForm company={company} posting={posting} />
    </main>
  );
}
