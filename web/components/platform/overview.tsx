import Link from "next/link";

import { KpiCard } from "@/components/ui/kpi-card";
import type { components } from "@/lib/api/client";

export type PlatformMetrics = components["schemas"]["MetricsOut"];

const pounds = (pence: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(pence / 100);

/** Where each admin screen lives on the admin host (public paths, never `/platform/...`). */
export const ADMIN_LINKS: readonly { href: string; label: string }[] = [
  { href: "/companies", label: "Companies" },
  { href: "/users", label: "Users" },
  { href: "/subscriptions", label: "Subscriptions and refunds" },
  { href: "/deletions", label: "Deletion and export queues" },
  { href: "/jobs", label: "Jobs" },
  { href: "/audit", label: "Audit log" },
  { href: "/rules", label: "SOC rules" },
  { href: "/courses", label: "Courses" },
  { href: "/dossier-links", label: "Dossier links" },
];

/** The admin landing page: platform figures as cards, then a list of every admin screen. */
export function PlatformOverview({
  metrics,
  queueWaiting,
}: {
  metrics: PlatformMetrics | null;
  queueWaiting: number | null;
}) {
  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="text-headline">Platform admin</h1>
      {metrics ? (
        <section
          aria-label="Platform figures"
          className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <KpiCard label="Signups, 24 hours" value={metrics.signups_24h} />
          <KpiCard label="Signups, 7 days" value={metrics.signups_7d} />
          <KpiCard label="Active companies" value={metrics.companies_active} />
          <KpiCard
            label="Plans"
            value={Object.values(metrics.plans_active).reduce((a, b) => a + b, 0)}
            subLabel={Object.entries(metrics.plans_active)
              .map(([plan, n]) => `${plan}: ${n}`)
              .join(" · ")}
          />
          <KpiCard label="Paid and entitled" value={metrics.paid_entitled} />
          <KpiCard
            label="MRR estimate"
            value={metrics.mrr_pence}
            format={pounds}
            subLabel={`ARR estimate ${pounds(metrics.arr_pence)}`}
          />
          <KpiCard label="Churn, 30 days" value={metrics.churn_30d} />
          <KpiCard label="Refunds, 30 days" value={metrics.refunds_30d} />
          {queueWaiting !== null ? (
            <KpiCard label="Job queue depth" value={queueWaiting} subLabel="Jobs waiting" />
          ) : null}
        </section>
      ) : (
        <p role="alert" className="text-body text-label-secondary mt-6">
          We could not load the platform figures. Reload the page to try again.
        </p>
      )}
      <nav aria-label="Admin screens" className="mt-8">
        <ul className="grid gap-2 sm:grid-cols-2">
          {ADMIN_LINKS.map((l) => (
            <li key={l.href}>
              <Link href={l.href} className="text-accent-text underline-offset-2 hover:underline">
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
