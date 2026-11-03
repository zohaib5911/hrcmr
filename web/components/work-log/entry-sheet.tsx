"use client";

import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { SheetContent } from "@/components/ui/sheet";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

export type Entry = components["schemas"]["WorkLogOut"];
export type Responsibility = components["schemas"]["OwnResponsibility"];

export function EntryDetails({ row }: { row: Entry }) {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-headline">
        {row.employee_name} · {formatUk(row.date)}
      </p>
      <p>
        {row.from_time.slice(0, 5)} to {row.to_time.slice(0, 5)} · {row.hours} hours
      </p>
      <p className="whitespace-pre-wrap break-words">{row.responsibility_text}</p>
      <p className="whitespace-pre-wrap break-words">{row.description}</p>
      {row.removed_at && <Alert title="This entry was removed" />}
      {row.corrected_from && (
        <section
          aria-label="Original work log entry"
          className="border-separator rounded-card border p-4"
        >
          <h3 className="text-headline mb-2">Original entry</h3>
          <p>
            {String(row.corrected_from.date)} · {String(row.corrected_from.from_time).slice(0, 5)}{" "}
            to {String(row.corrected_from.to_time).slice(0, 5)}
          </p>
          <p className="whitespace-pre-wrap break-words">
            {String(row.corrected_from.responsibility_text ?? "")}
          </p>
          <p className="whitespace-pre-wrap break-words">
            {String(row.corrected_from.description ?? "")}
          </p>
        </section>
      )}
    </div>
  );
}

export function WorkLogSheet({
  row,
  mode,
  responsibilities,
  today,
  timezone,
  saved,
}: {
  row: Entry | null;
  mode: "new" | "edit" | "correct" | "view";
  responsibilities: Responsibility[];
  today: string;
  timezone: string;
  saved: () => void;
}) {
  const [date, setDate] = useState(row?.date ?? today);
  const [start, setStart] = useState(row?.from_time.slice(0, 5) ?? "09:00");
  const [end, setEnd] = useState(row?.to_time.slice(0, 5) ?? "17:00");
  const [responsibility, setResponsibility] = useState(row?.responsibility_id ?? "");
  const [words, setWords] = useState(row?.responsibility_text ?? "");
  const [description, setDescription] = useState(row?.description ?? "");
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const options =
    row?.responsibility_id && !responsibilities.some((r) => r.id === row.responsibility_id)
      ? [{ id: row.responsibility_id, text: row.responsibility_text }, ...responsibilities]
      : responsibilities;
  const title =
    mode === "new"
      ? "Add work log"
      : mode === "edit"
        ? "Edit work log"
        : mode === "correct"
          ? "Correct work log"
          : "Work log entry";
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem(null);
    const body = {
      date,
      from_time: start,
      to_time: end,
      responsibility_id: responsibility || null,
      responsibility_text: responsibility ? null : words,
      description,
    };
    const result = await (mode === "new"
      ? attempt((c) => c.POST("/work-log/own", { body }))
      : mode === "edit" && row
        ? attempt((c) =>
            c.PATCH("/work-log/own/{entry_id}", {
              params: { path: { entry_id: row.id } },
              body: { ...body, revision: row.revision },
            }),
          )
        : attempt((c) =>
            c.POST("/work-log/{entry_id}/correct", {
              params: { path: { entry_id: row!.id } },
              body: { ...body, revision: row!.revision, reason },
            }),
          ));
    setBusy(false);
    if (result.ok) saved();
    else setProblem(result.problem);
  }
  if (mode === "view" && row)
    return (
      <SheetContent title={title} readOnly>
        <EntryDetails row={row} />
      </SheetContent>
    );
  return (
    <SheetContent
      title={title}
      description={`Times use ${timezone}. An earlier finish ends the following day.`}
    >
      <form className="flex flex-col gap-4" onSubmit={(e) => void submit(e)}>
        {problem && <Alert tone="danger" title={problem.message} />}
        {row && <p className="text-headline">{row.employee_name}</p>}
        <TextField
          label="Work date"
          type="date"
          required
          max={today}
          value={date}
          disabled={busy || mode === "edit"}
          onChange={(e) => setDate(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="From"
            type="time"
            required
            value={start}
            disabled={busy}
            onChange={(e) => setStart(e.target.value)}
          />
          <TextField
            label="To"
            type="time"
            required
            value={end}
            disabled={busy}
            onChange={(e) => setEnd(e.target.value)}
          />
        </div>
        <Select
          label="Responsibility"
          value={responsibility}
          disabled={busy}
          onChange={(e) => setResponsibility(e.target.value)}
        >
          <option value="">Use my own words</option>
          {options.map((r) => (
            <option key={r.id} value={r.id}>
              {r.text}
            </option>
          ))}
        </Select>
        {!responsibility && (
          <TextArea
            label="Responsibility in my own words"
            required
            maxLength={2000}
            disabled={busy}
            value={words}
            onChange={(e) => setWords(e.target.value)}
          />
        )}
        <TextArea
          label="What I did"
          required
          maxLength={4000}
          disabled={busy}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        {mode === "correct" && (
          <>
            <TextArea
              label="Reason for correction"
              required
              maxLength={1000}
              disabled={busy}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            <p className="text-callout text-label-secondary">
              The original entry is retained. Your correction and reason are audited.
            </p>
          </>
        )}
        <div>
          <Button type="submit" loading={busy}>
            {mode === "correct" ? "Save correction" : "Save entry"}
          </Button>
        </div>
      </form>
    </SheetContent>
  );
}
