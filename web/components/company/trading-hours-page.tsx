"use client";

import { Check } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Icon } from "@/components/ui/icon";
import { TimePicker } from "@/components/ui/time-picker";
import { Toggle } from "@/components/ui/toggle";
import type { components } from "@/lib/api/client";
import { attempt } from "@/lib/auth/request";
import { WEEKDAYS } from "@/lib/company/working-pattern";
import { dayProblem, hhmm, openSummary, SUGGESTED_OPENING } from "@/lib/company/trading-hours";

type Hours = components["schemas"]["TradingHours"];

type Row = {
  weekday: number;
  is_open: boolean;
  opens: string | null;
  closes: string | null;
  /** "saved" shows a tick for a moment; a string is what went wrong. */
  state: "idle" | "saving" | "saved" | string;
};

/** `/company/trading-hours` (plan 8.15): when the business is open. Each row saves by itself. */
export function TradingHoursPage({ hours }: { hours: Hours }) {
  const mayEdit = useCan()("company.profile.write");
  const [rows, setRows] = useState<Row[]>(
    hours.days.map((day) => ({
      weekday: day.weekday,
      is_open: day.is_open,
      opens: hhmm(day.opens_at),
      closes: hhmm(day.closes_at),
      state: "idle",
    })),
  );

  function patch(weekday: number, change: Partial<Row>) {
    setRows((current) => current.map((r) => (r.weekday === weekday ? { ...r, ...change } : r)));
  }

  async function save(next: Row) {
    const problem = next.is_open ? dayProblem(next.opens, next.closes) : null;
    if (problem) {
      patch(next.weekday, { ...next, state: problem });
      return;
    }
    patch(next.weekday, { ...next, state: "saving" });
    const outcome = await attempt((client) =>
      client.PUT("/trading-hours/{weekday}", {
        params: { path: { weekday: next.weekday } },
        body: {
          is_open: next.is_open,
          opens_at: next.is_open ? next.opens : null,
          closes_at: next.is_open ? next.closes : null,
        },
      }),
    );
    patch(next.weekday, { state: outcome.ok ? "saved" : outcome.problem.message });
    if (outcome.ok) setTimeout(() => patch(next.weekday, { state: "idle" }), 2500);
  }

  return (
    <>
      <PageHeader
        title="Trading hours"
        description={`${openSummary(rows)}. Each day saves as you change it.`}
      />
      <ul className="bg-elevated rounded-card shadow-e1 divide-separator divide-y overflow-hidden max-w-2xl">
        {rows.map((row) => {
          const name = WEEKDAYS[row.weekday - 1] ?? "";
          const failed = row.state !== "idle" && row.state !== "saving" && row.state !== "saved";
          return (
            <li key={row.weekday} className="flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
              <div className="min-w-40 flex-1">
                <Toggle
                  label={name}
                  checked={row.is_open}
                  disabled={!mayEdit}
                  onCheckedChange={(checked) =>
                    void save({
                      ...row,
                      is_open: checked,
                      opens: checked ? (row.opens ?? SUGGESTED_OPENING.opens) : null,
                      closes: checked ? (row.closes ?? SUGGESTED_OPENING.closes) : null,
                    })
                  }
                />
              </div>
              <TimePicker
                label="Opens"
                aria-label={`${name} opens`}
                containerClassName="w-36"
                value={row.opens}
                disabled={!mayEdit || !row.is_open}
                onChange={(value) => void save({ ...row, opens: value })}
              />
              <TimePicker
                label="Closes"
                aria-label={`${name} closes`}
                containerClassName="w-36"
                value={row.closes}
                disabled={!mayEdit || !row.is_open}
                onChange={(value) => void save({ ...row, closes: value })}
              />
              <p
                role="status"
                className={
                  failed
                    ? "text-subheadline text-danger basis-full"
                    : "text-subheadline text-label-secondary flex w-16 items-center gap-1"
                }
              >
                {row.state === "saved" ? (
                  <>
                    <Icon icon={Check} size={16} /> Saved
                  </>
                ) : failed ? (
                  row.state
                ) : null}
              </p>
            </li>
          );
        })}
      </ul>
    </>
  );
}
