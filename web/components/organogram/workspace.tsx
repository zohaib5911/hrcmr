"use client";

import dynamic from "next/dynamic";
import { Network } from "lucide-react";
import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchField } from "@/components/ui/search-field";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { SkeletonCard } from "@/components/ui/skeleton";
import { Toggle } from "@/components/ui/toggle";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

import type { CanvasHandle } from "./canvas";
const OrgCanvas = dynamic(() => import("./canvas").then((m) => m.OrgCanvas), {
  loading: () => <SkeletonCard />,
});
import { PersonInspector } from "./inspector";
import { findPeople, flatten, layoutTree, type OrgPerson } from "./layout";
import { OrgList } from "./list-view";

type Chart = components["schemas"]["OrgChartOut"];
type Mode = "chart" | "list";

const segments: { value: Mode; label: string }[] = [
  { value: "chart", label: "Chart" },
  { value: "list", label: "List" },
];

/** The org chart page: a search, a chart or list of everyone, and a summary card per person. */
export function OrgChartWorkspace() {
  const [chart, setChart] = useState<Chart | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [mode, setMode] = useState<Mode>("chart");
  const [query, setQuery] = useState("");
  const [showVisa, setShowVisa] = useState(false);
  const [selected, setSelected] = useState<OrgPerson | null>(null);
  const [busy, setBusy] = useState(false);
  const canvas = useRef<CanvasHandle>(null);

  useEffect(() => {
    let active = true;
    void attempt((c) => c.GET("/organogram")).then((result) => {
      if (!active) return;
      if (result.ok) setChart(result.data);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, []);

  const roots = useMemo(() => chart?.unassigned ?? [], [chart]);
  const layout = useMemo(() => layoutTree(roots), [roots]);
  const rows = useMemo(() => flatten(roots), [roots]);
  const matches = useMemo(() => findPeople(roots, query), [roots, query]);
  const rtwVisible = chart?.rtw_visible ?? false;
  const empty = chart !== null && roots.length === 0;

  function open(person: OrgPerson) {
    setSelected(person);
  }

  function jumpTo(person: OrgPerson) {
    setSelected(person);
    canvas.current?.centreOn(person.id);
  }

  function onSearchKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && matches[0]) {
      event.preventDefault();
      jumpTo(matches[0]);
    }
  }

  async function downloadPdf() {
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) => c.GET("/organogram.pdf", { parseAs: "blob" }));
    setBusy(false);
    if (!result.ok) {
      setProblem(result.problem);
      return;
    }
    const url = URL.createObjectURL(result.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "org-chart.pdf";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <PageHeader
        title="Org chart"
        description="Who reports to whom, from each person's Reporting Authority."
        actions={
          <Button variant="gray" disabled={busy || chart === null} onClick={downloadPdf}>
            Download PDF
          </Button>
        }
      />
      {problem ? <Alert tone="danger" title={problem.message} className="mb-6" /> : null}
      {chart === null && !problem ? <SkeletonCard className="h-80" /> : null}
      {empty ? (
        <EmptyState
          icon={Network}
          title="No org chart yet"
          description="Your reporting lines will be drawn here once people have a manager and a department."
        />
      ) : null}
      {chart !== null && !empty ? (
        <section aria-labelledby="unassigned-heading" className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h2 id="unassigned-heading" className="text-title-3 text-label">
              Unassigned
            </h2>
            <p className="text-footnote text-label-secondary">
              {roots.length} {roots.length === 1 ? "person" : "people"} without a Reporting
              Authority, with the people who report to them.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="min-w-60 flex-1">
              <SearchField
                label="Search people"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={onSearchKey}
              />
            </div>
            <SegmentedControl<Mode>
              label="View"
              size="sm"
              value={mode}
              onValueChange={setMode}
              segments={segments}
            />
            {rtwVisible ? (
              <Toggle label="Show visa status" checked={showVisa} onCheckedChange={setShowVisa} />
            ) : null}
          </div>
          {matches.length > 0 ? (
            <ul aria-label="Matching people" className="flex flex-wrap gap-2">
              {matches.map((person) => (
                <li key={person.id}>
                  <Button variant="gray" size="sm" onClick={() => jumpTo(person)}>
                    {person.name}
                    {person.job_title ? ` · ${person.job_title}` : ""}
                  </Button>
                </li>
              ))}
            </ul>
          ) : query.trim() ? (
            <p role="status" className="text-footnote text-label-secondary">
              No one matches “{query.trim()}”.
            </p>
          ) : null}
          {mode === "chart" ? (
            <OrgCanvas
              layout={layout}
              showVisa={showVisa && rtwVisible}
              selectedId={selected?.id ?? null}
              onOpen={open}
              handle={canvas}
            />
          ) : (
            <OrgList rows={rows} rtwVisible={rtwVisible} onOpen={open} />
          )}
        </section>
      ) : null}
      <PersonInspector
        person={selected}
        rtwVisible={rtwVisible}
        onClose={() => setSelected(null)}
      />
    </>
  );
}
