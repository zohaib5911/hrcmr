"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { MenuItem } from "@/components/ui/menu";
import { Sheet } from "@/components/ui/sheet";
import { DatePicker } from "@/components/ui/date-picker";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { downloadBlob } from "@/lib/attendance";
import { attempt, type Problem } from "@/lib/auth/request";
import { addDays, formatUk, parseIso, startOfWeek, todayIso } from "@/lib/ui/dates";
import { RotaShiftSheet, templateTimes, type RotaShift, type ShiftTemplate } from "./shift-sheet";

export type Week = components["schemas"]["WeekOut"];
export type Person = Week["people"][number];
export type ActionKind =
  | "clear"
  | "copy-last-week"
  | "copy-employee-week"
  | "clear-employee-week"
  | "copy-day"
  | "publish";
export type Action = {
  kind: ActionKind;
  title: string;
  week: string;
  version: number;
  employee_id?: string;
  on?: string;
  source?: string;
  targets?: string[];
};

import { ActionMenu } from "./action-menu";
const WeekGrid = dynamic(() => import("./week-grid").then((m) => m.WeekGrid));

export function RotaWorkspace({ initialWeek }: { initialWeek?: string }) {
  const can = useCan();
  const writable = can("rota.duty_roster.write", "rota.duty_roster.write_reports");
  const [start, setStart] = useState(() =>
    initialWeek && parseIso(initialWeek) ? startOfWeek(initialWeek) : startOfWeek(todayIso()),
  );
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [data, setData] = useState<Week | null>(null);
  const [templates, setTemplates] = useState<ShiftTemplate[]>([]);
  const [quick, setQuick] = useState<string | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const [loaded, setLoaded] = useState("");
  const [opened, setOpened] = useState<{
    row: RotaShift | null;
    person: Person;
    date: string;
    version: number;
  } | null>(null);
  const [action, setAction] = useState<Action | null>(null);
  const key = `${start}:${offset}:${search}:${version}`;
  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/rota/weeks/{week_start}", {
        params: { path: { week_start: start }, query: { offset, search } },
      }),
    ).then((result) => {
      if (!active) return;
      setLoaded(key);
      if (result.ok) setData(result.data);
      else {
        setData(null);
        setProblem(result.problem);
      }
    });
    return () => {
      active = false;
    };
  }, [start, offset, search, version, key]);
  useEffect(() => {
    let active = true;
    void attempt((c) => c.GET("/rota/shift-types")).then((result) => {
      if (active && result.ok) setTemplates(result.data);
    });
    return () => {
      active = false;
    };
  }, []);
  const current = loaded === key ? data : null;
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const today = current
    ? new Intl.DateTimeFormat("en-CA", {
        timeZone: current.timezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(new Date())
    : todayIso();
  const reload = () => setVersion((v) => v + 1);
  function ask(kind: ActionKind, title: string, extra: Partial<Action> = {}) {
    if (!current) return;
    setProblem(null);
    setNotice(null);
    setAction({ kind, title, week: start, version: current.version, ...extra });
  }
  async function confirm() {
    if (!action) return;
    setBusy(true);
    setProblem(null);
    const path = { path: { week_start: action.week } };
    const body = { version: action.version };
    const result = await (action.kind === "publish"
      ? attempt((c) => c.POST("/rota/weeks/{week_start}/publish", { params: path, body }))
      : action.kind === "copy-last-week"
        ? attempt((c) => c.POST("/rota/weeks/{week_start}/copy-last-week", { params: path, body }))
        : action.kind === "clear"
          ? attempt((c) =>
              c.POST("/rota/weeks/{week_start}/clear", {
                params: path,
                body: { ...body, on: action.on },
              }),
            )
          : action.kind === "copy-day"
            ? attempt((c) =>
                c.POST("/rota/weeks/{week_start}/copy-day", {
                  params: path,
                  body: { ...body, source: action.source!, targets: action.targets! },
                }),
              )
            : action.kind === "copy-employee-week"
              ? attempt((c) =>
                  c.POST("/rota/weeks/{week_start}/copy-employee-week", {
                    params: path,
                    body: { ...body, employee_id: action.employee_id! },
                  }),
                )
              : attempt((c) =>
                  c.POST("/rota/weeks/{week_start}/clear-employee-week", {
                    params: path,
                    body: { ...body, employee_id: action.employee_id! },
                  }),
                ));
    setBusy(false);
    if (result.ok) {
      setNotice(
        action.kind === "publish" ? "Rota published" : `${result.data.count} shifts updated`,
      );
      setAction(null);
      reload();
    } else setProblem(result.problem);
  }
  async function cell(person: Person, day: string) {
    if (!current || busy) return;
    const template = templates.find((t) => t.id === quick);
    if (!template) {
      setOpened({ row: null, person, date: day, version: current.version });
      return;
    }
    setBusy(true);
    setProblem(null);
    setNotice(null);
    const result = await attempt((c) =>
      c.POST("/rota/scheduled-shifts", {
        body: {
          ...templateTimes(template),
          employee_id: person.id,
          date: day,
          version: current.version,
        },
      }),
    );
    setBusy(false);
    if (result.ok) {
      setNotice("Shift added");
      reload();
    } else setProblem(result.problem);
  }
  async function print() {
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/rota/weeks/{week_start}/print.pdf", {
        params: { path: { week_start: start } },
        parseAs: "blob",
      }),
    );
    setBusy(false);
    if (result.ok) downloadBlob(result.data, `rota-${start}.pdf`);
    else setProblem(result.problem);
  }
  return (
    <>
      <PageHeader
        title="Rota"
        description="Plan shifts, review warnings and publish the week."
        actions={
          <>
            <Button asChild variant="gray">
              <Link href="/rota/settings">Shift types and settings</Link>
            </Button>
            <Button asChild variant="gray">
              <Link href="/my-shifts">My shifts</Link>
            </Button>
            <Button variant="gray" disabled={busy || !current} onClick={() => void print()}>
              Print rota PDF
            </Button>
          </>
        }
      />
      <div className="flex min-w-0 flex-col gap-5">
        {problem && !action && (
          <Alert tone="danger" title={problem.message}>
            <Button
              variant="gray"
              onClick={() => {
                setProblem(null);
                reload();
              }}
            >
              Reload week
            </Button>
          </Alert>
        )}
        {notice && <Alert tone="success" title={notice} />}
        <div className="flex flex-wrap items-end gap-3">
          <Button
            variant="gray"
            disabled={busy}
            onClick={() => {
              setStart(addDays(start, -7));
              setOffset(0);
            }}
          >
            Previous week
          </Button>
          <DatePicker
            label="Rota week containing"
            value={start || null}
            disabled={busy}
            onChange={(picked) => {
              if (picked ?? "") {
                setStart(startOfWeek(picked ?? ""));
                setOffset(0);
              }
            }}
          />
          <Button
            variant="gray"
            disabled={busy}
            onClick={() => {
              setStart(addDays(start, 7));
              setOffset(0);
            }}
          >
            Next week
          </Button>
          <TextField
            label="Find someone"
            value={search}
            maxLength={100}
            disabled={busy}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
          <Button variant="gray" disabled={busy} onClick={reload}>
            Reload week
          </Button>
        </div>
        {current && (
          <>
            <Alert
              tone={current.status === "published" ? "success" : "warning"}
              title={
                current.status === "published"
                  ? "Published rota"
                  : current.published_at
                    ? "Changes not published"
                    : "Draft rota — not visible to employees yet"
              }
            >
              Employees see the last published schedule. Actions apply only to employees you can
              manage.
            </Alert>
            {writable && (
              <div className="flex flex-wrap items-center gap-3">
                <Button disabled={busy} onClick={() => ask("publish", "Publish this week?")}>
                  Publish week
                </Button>
                <Button
                  variant="gray"
                  disabled={busy}
                  onClick={() =>
                    ask("copy-last-week", "Replace this week with last week's shifts?")
                  }
                >
                  Copy last week
                </Button>
                <ActionMenu label="Week actions" disabled={busy}>
                  <MenuItem destructive onSelect={() => ask("clear", "Clear this whole week?")}>
                    Clear this whole week
                  </MenuItem>
                </ActionMenu>
              </div>
            )}
            {writable && !!templates.length && (
              <div>
                <p className="text-callout text-label-secondary mb-2">
                  Quick add: choose a shift type, then click an Add cell. Click the type again to
                  open a sheet instead.
                </p>
                <div
                  role="group"
                  aria-label="Quick add shift types"
                  className="flex flex-wrap gap-2"
                >
                  {templates.map((t) => (
                    <Button
                      key={t.id}
                      variant={quick === t.id ? "tinted" : "gray"}
                      aria-pressed={quick === t.id}
                      disabled={busy}
                      onClick={() => setQuick(quick === t.id ? null : t.id)}
                    >
                      {t.name}
                    </Button>
                  ))}
                </div>
              </div>
            )}
            <p className="text-caption text-label-secondary">
              {formatUk(start)} to {formatUk(addDays(start, 6))} · {current.timezone} · Totals cover
              employees shown.
            </p>
            <WeekGrid
              current={current}
              days={days}
              today={today}
              writable={writable}
              busy={busy}
              ask={ask}
              cell={cell}
              setOpened={setOpened}
            />
            <section aria-label="Not scheduled this week">
              <h2 className="text-headline">
                Not scheduled this week ({current.not_scheduled.length})
              </h2>
              <p className="text-caption text-label-secondary">Among employees shown.</p>
              <ul className="mt-2 flex flex-wrap gap-3">
                {current.people
                  .filter((p) => current.not_scheduled.includes(p.id))
                  .map((p) => (
                    <li key={p.id}>{p.name}</li>
                  ))}
              </ul>
            </section>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="gray"
                disabled={busy || !offset}
                onClick={() => setOffset(Math.max(0, offset - 20))}
              >
                Previous employees
              </Button>
              <Button
                variant="gray"
                disabled={busy || current.next_offset == null}
                onClick={() => setOffset(current.next_offset ?? 0)}
              >
                Next employees
              </Button>
            </div>
          </>
        )}
        {!current && !problem && <p role="status">Loading rota…</p>}
      </div>
      <Sheet
        open={opened !== null}
        onOpenChange={(open) => {
          if (!open) setOpened(null);
        }}
      >
        {opened && data && (
          <RotaShiftSheet
            key={opened.row?.id ?? `${opened.person.id}:${opened.date}`}
            row={opened.row}
            employee={{
              value: opened.person.id,
              label: opened.person.name,
              description: opened.person.employee_number,
            }}
            date={opened.date}
            week={start}
            version={opened.version}
            timezone={data.timezone}
            templates={templates}
            writable={opened.person.can_write}
            saved={() => {
              setOpened(null);
              setProblem(null);
              reload();
            }}
          />
        )}
      </Sheet>
      <Dialog
        open={action !== null}
        onOpenChange={(open) => {
          if (!open && !busy) {
            setAction(null);
            setProblem(null);
          }
        }}
      >
        <DialogContent
          title={action?.title ?? "Review rota action"}
          footer={
            <>
              <Button
                variant="gray"
                disabled={busy}
                onClick={() => {
                  setAction(null);
                  setProblem(null);
                }}
              >
                Cancel
              </Button>
              <Button
                variant={action?.kind === "publish" ? "filled" : "destructive"}
                loading={busy}
                onClick={() => void confirm()}
              >
                Confirm {action?.kind === "publish" ? "publication" : "changes"}
              </Button>
            </>
          }
        >
          <p>
            {action?.kind === "publish"
              ? "Employees will see the updated schedule and receive a notification. Review warnings before publishing."
              : "Existing shifts in the selected scope will be replaced or removed. The change is saved as a draft."}
          </p>
          {problem && <Alert tone="danger" title={problem.message} />}
        </DialogContent>
      </Dialog>
    </>
  );
}
