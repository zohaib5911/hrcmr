"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { attempt } from "@/lib/auth/request";
import type { components, paths } from "@/lib/api/client";
import { REGIONS, RegionMap, type RegionCount } from "./region-map";

type Data = components["schemas"]["ExploreOut"];
type Sponsor = components["schemas"]["SponsorOut"];
type Bucket = components["schemas"]["Bucket"];
type Query = NonNullable<paths["/public/register/explore"]["get"]["parameters"]["query"]>;
type View = "Map" | "Trend" | "Table" | "List";
const control =
  "bg-elevated border-separator text-label rounded-control min-h-11 w-full border px-3 py-2";
const number = (n: number) => n.toLocaleString("en-GB");
const signed = (n: number) => `${n > 0 ? "+" : ""}${number(n)}`;
const windows = [
  ["7", "7 days"],
  ["30", "30 days"],
  ["90", "90 days"],
  ["180", "180 days"],
  ["365", "1 year"],
  ["start", "From start"],
] as const;
const industries: Record<string, string> = {
  A: "Agriculture, forestry and fishing",
  B: "Mining and quarrying",
  C: "Manufacturing",
  D: "Electricity and gas",
  E: "Water and waste",
  F: "Construction",
  G: "Wholesale and retail",
  H: "Transport and storage",
  I: "Accommodation and food",
  J: "Information and communication",
  K: "Finance and insurance",
  L: "Real estate",
  M: "Professional, scientific and technical",
  N: "Administration and support",
  O: "Public administration",
  P: "Education",
  Q: "Health and social work",
  R: "Arts and recreation",
  S: "Other services",
  T: "Households",
  U: "Extraterritorial organisations",
};
const industryName = (key: string) => (industries[key] ? `${key} — ${industries[key]}` : key);

function Breakdown({
  title,
  rows,
  industry = false,
}: {
  title: string;
  rows: Bucket[];
  industry?: boolean;
}) {
  return (
    <Card>
      <CardHeader title={title} headingLevel={2} />
      <CardBody>
        {rows.length ? (
          <dl className="space-y-2">
            {rows.map((r) => (
              <div key={r.label} className="flex justify-between gap-4">
                <dt className="break-words">{industry ? industryName(r.label) : r.label}</dt>
                <dd className="tabular-nums">{number(r.count)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p>No matching sponsors.</p>
        )}
        {rows.length === 50 && <p className="text-footnote mt-3">Showing the 50 largest groups.</p>}
      </CardBody>
    </Card>
  );
}

function SponsorList({ rows }: { rows: Sponsor[] }) {
  return (
    <ul className="divide-separator divide-y">
      {rows.map((s) => (
        <li key={s.id} className="py-4">
          <h3 className="text-headline">{s.name}</h3>
          <p>
            {s.town || "Town unknown"} · {s.region ?? "Region unknown"}
          </p>
          <p className="text-label-secondary text-subheadline">
            {s.routes.join(" · ")} — {s.ratings.join(" · ")}
          </p>
          <p className="text-footnote">
            First seen {s.first_seen} · {industryName(s.industry ?? "Industry unknown")}
          </p>
        </li>
      ))}
    </ul>
  );
}

function HistoryChart({
  points,
  trend = false,
}: {
  points: NonNullable<Data["timeline"]>;
  trend?: boolean;
}) {
  const peak = Math.max(1, ...points.map((p) => (trend ? p.count : Math.max(p.added, p.removed))));
  return (
    <figure className="min-w-0">
      <svg
        role="img"
        aria-label={
          trend
            ? "Sponsor count by publication"
            : "Register pulse: added above and removed below the centre line"
        }
        viewBox="0 0 800 210"
        className="h-auto max-h-64 w-full text-accent-text"
      >
        <line x1="0" x2="800" y1={trend ? 200 : 105} y2={trend ? 200 : 105} stroke="currentColor" />
        {points.map((p, i) => {
          const width = 800 / Math.max(1, points.length);
          const above = ((trend ? p.count : p.added) / peak) * 95;
          return (
            <g key={`${p.published_on}-${i}`}>
              <title>
                {p.published_on}: {number(p.count)} sponsors; {p.added} added or returned;{" "}
                {p.removed} no longer listed
              </title>
              <rect
                x={i * width + 1}
                y={(trend ? 200 : 105) - above}
                width={Math.max(0.5, width - 2)}
                height={above}
                fill="currentColor"
              />
              {!trend && (
                <rect
                  x={i * width + 1}
                  y="105"
                  width={Math.max(0.5, width - 2)}
                  height={(p.removed / peak) * 95}
                  fill="currentColor"
                  fillOpacity="0.5"
                />
              )}
            </g>
          );
        })}
      </svg>
      <figcaption className="text-label-secondary text-footnote">
        {points[0]?.published_on} to {points.at(-1)?.published_on}.{" "}
        {trend
          ? "One bar per publication."
          : "Added (including returned) above; no longer listed below. All values follow your filters."}
      </figcaption>
      <details className="mt-3">
        <summary className="cursor-pointer text-accent-text">View chart data</summary>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-subheadline">
            <caption className="sr-only">Publication chart values</caption>
            <thead>
              <tr>
                {["Publication", "Sponsors", "Added / returned", "No longer listed"].map(
                  (label) => (
                    <th className="p-2" scope="col" key={label}>
                      {label}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {points.map((p, i) => (
                <tr key={`${p.published_on}-${i}`}>
                  <th scope="row" className="p-2">
                    {p.published_on}
                  </th>
                  <td>{number(p.count)}</td>
                  <td>{number(p.added)}</td>
                  <td>{number(p.removed)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

export function RegisterExplorer() {
  const [query, setQuery] = useState<Query>({ window: "30", page: 1 });
  const [search, setSearch] = useState("");
  const [view, setView] = useState<View>("Map");
  const [retry, setRetry] = useState(0);
  const [response, setResponse] = useState<{ key: string; data?: Data; error?: string }>();
  const requestKey = JSON.stringify([query, retry]);
  useEffect(() => {
    let active = true;
    void attempt((client) => client.GET("/public/register/explore", { params: { query } })).then(
      (outcome) => {
        if (active)
          setResponse(
            outcome.ok
              ? { key: requestKey, data: outcome.data }
              : { key: requestKey, error: outcome.problem.message },
          );
      },
    );
    return () => {
      active = false;
    };
  }, [query, requestKey]);
  const loading = response?.key !== requestKey;
  const data = response?.data;
  const update = (patch: Partial<Query>) =>
    setQuery((current) => ({ ...current, page: 1, ...patch }));
  const selectedIndex = Math.max(
    0,
    data?.publications?.findIndex((p) => p.id === data.selected?.id) ?? 0,
  );
  const counts: Record<string, RegionCount> = {};
  for (const region of REGIONS) {
    const count = data?.sections?.regions?.find((r) => r.label === region.name)?.count ?? 0;
    const previous = data?.daily_previous_regions?.find((r) => r.label === region.name)?.count ?? 0;
    counts[region.name] = { count, delta: count - previous };
  }
  return (
    <div className="space-y-6">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          update({ q: search });
        }}
      >
        <label className="min-w-0 flex-1">
          Search sponsor, town or route
          <input
            className={`${control} mt-1`}
            type="search"
            maxLength={100}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <Button type="submit">Search register</Button>
      </form>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {(
          [
            ["region", "Region"],
            ["route", "Route"],
            ["rating", "Rating and licence"],
            ["industry", "Industry"],
          ] as const
        ).map(([key, label]) => (
          <label key={key}>
            {label}
            <select
              className={`${control} mt-1`}
              value={query[key] ?? ""}
              onChange={(event) => update({ [key]: event.target.value })}
            >
              <option value="">All {label.toLowerCase()}</option>
              {(data?.facets?.[key] ?? []).map((value) => (
                <option key={value} value={value}>
                  {key === "industry" ? industryName(value) : value}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <Button
        variant="plain"
        onClick={() => {
          setSearch("");
          setQuery({ window: "30", page: 1 });
        }}
      >
        Reset filters
      </Button>
      <div role="status" aria-live="polite">
        {loading
          ? "Loading register…"
          : response?.error
            ? ""
            : !data?.selected
              ? "No register publications are available yet."
              : `${number(data.total ?? 0)} matching sponsors in the selected publication.`}
      </div>
      {!loading && response?.error && (
        <div role="alert" className="space-y-3">
          <p>{response.error}</p>
          <Button onClick={() => setRetry((n) => n + 1)}>Try again</Button>
        </div>
      )}
      {data?.selected && (
        <section
          aria-label="Publication controls"
          className="bg-elevated rounded-card space-y-4 p-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p>
              Publication: <strong>{data.selected.published_on}</strong> ·{" "}
              <a className="text-accent-text underline" href={data.selected.source_url}>
                GOV.UK source CSV
              </a>
            </p>
            <label>
              Compare window
              <select
                className={`${control} mt-1`}
                value={query.window}
                onChange={(event) => update({ window: event.target.value as Query["window"] })}
              >
                {windows.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="block">
            Publication timeline
            <input
              aria-valuetext={data.selected.published_on}
              type="range"
              className="mt-2 w-full"
              min={0}
              max={Math.max(0, (data.publications?.length ?? 0) - 1)}
              step={1}
              value={selectedIndex}
              disabled={(data.publications?.length ?? 0) < 2}
              onChange={(event) =>
                update({ publication_id: data.publications?.[Number(event.target.value)]?.id })
              }
            />
          </label>
          <p className="text-footnote text-label-secondary">
            Comparison starts at {data.baseline?.published_on}. If the requested date predates our
            archive, we use the first available publication. Daily deltas compare with the last
            publication on a previous day; with no earlier day, the delta is zero.
          </p>
        </section>
      )}
      {!loading && data?.selected && (
        <div className="space-y-6">
          <Card>
            <CardHeader title="Then and now" headingLevel={2} />
            <CardBody>
              <p className="text-title-2 tabular-nums">
                {number(data.previous_total ?? 0)} → {number(data.total ?? 0)} sponsors{" "}
                <span className="text-label-secondary">
                  ({signed((data.total ?? 0) - (data.previous_total ?? 0))})
                </span>
              </p>
              <p className="text-footnote mt-2">
                {data.baseline?.published_on} compared with {data.selected.published_on}. Route,
                rating and type groups may overlap.
              </p>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Register pulse" headingLevel={2} />
            <CardBody>
              <HistoryChart points={data.timeline ?? []} />
            </CardBody>
          </Card>
          <div role="group" aria-label="Register view" className="flex flex-wrap gap-2">
            {(["Map", "Trend", "Table", "List"] as const).map((name) => (
              <Button
                key={name}
                aria-pressed={view === name}
                variant={view === name ? "filled" : "gray"}
                onClick={() => setView(name)}
              >
                {name}
              </Button>
            ))}
          </div>
          <section aria-label={`${view} view`}>
            {view === "Map" && (
              <div className="grid items-start gap-6 md:grid-cols-2">
                <RegionMap counts={counts} deltaLabel="since prior publication day" />
                <div>
                  <h2 className="text-title-2 mb-3">Regions at a glance</h2>
                  <dl className="space-y-2">
                    {REGIONS.map((r) => (
                      <div className="flex justify-between gap-3" key={r.name}>
                        <dt>{r.name}</dt>
                        <dd>
                          {number(counts[r.name]?.count ?? 0)} ({signed(counts[r.name]?.delta ?? 0)}
                          )
                        </dd>
                      </div>
                    ))}
                  </dl>
                  <p className="text-footnote mt-4">
                    Schematic map. Unknown placements are included in the totals and listed below.
                  </p>
                </div>
              </div>
            )}
            {view === "Trend" && <HistoryChart points={data.timeline ?? []} trend />}
            {view === "Table" && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-subheadline">
                  <caption className="sr-only">Matching sponsors</caption>
                  <thead>
                    <tr>
                      {["Sponsor", "Town", "Region", "Routes", "Rating and licence"].map(
                        (heading) => (
                          <th className="p-3" scope="col" key={heading}>
                            {heading}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {data.results?.map((s) => (
                      <tr key={s.id} className="border-separator border-t">
                        <th scope="row" className="p-3">
                          {s.name}
                        </th>
                        <td className="p-3">{s.town || "Unknown"}</td>
                        <td className="p-3">{s.region ?? "Unknown"}</td>
                        <td className="p-3">{s.routes.join("; ")}</td>
                        <td className="p-3">{s.ratings.join("; ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {view === "List" && <SponsorList rows={data.results ?? []} />}
            {data.total === 0 && (
              <p className="mt-4">
                No sponsors match these filters. Try a broader search or reset filters.
              </p>
            )}
          </section>
          {(view === "Table" || view === "List") && (
            <nav aria-label="Sponsor result pages" className="flex flex-wrap items-center gap-3">
              <Button
                variant="gray"
                disabled={(data.page ?? 1) <= 1}
                onClick={() => update({ page: (data.page ?? 1) - 1 })}
              >
                Previous page
              </Button>
              <span>
                Page {data.page} of{" "}
                {Math.max(1, Math.ceil((data.total ?? 0) / (data.page_size ?? 50)))}
              </span>
              <Button
                variant="gray"
                disabled={(data.page ?? 1) * (data.page_size ?? 50) >= (data.total ?? 0)}
                onClick={() => update({ page: (data.page ?? 1) + 1 })}
              >
                Next page
              </Button>
            </nav>
          )}
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {(
              [
                ["towns", "Sponsors by town"],
                ["regions", "Regions"],
                ["routes", "Routes"],
                ["ratings", "Ratings"],
                ["types", "Licence types"],
                ["precision", "Placement precision"],
                ["industries", "Industries"],
              ] as const
            ).map(([key, title]) => (
              <Breakdown
                key={key}
                title={title}
                rows={data.sections?.[key] ?? []}
                industry={key === "industries"}
              />
            ))}
          </div>
          <Card>
            <CardHeader
              title="Newest on the register"
              description="Up to 10 matching sponsors, ordered by first appearance in our archive."
              headingLevel={2}
            />
            <CardBody>
              <SponsorList rows={data.newest ?? []} />
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
}
