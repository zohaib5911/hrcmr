"use client";

import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Button, IconButton } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { GroupedEmpty, GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { Icon } from "@/components/ui/icon";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { Toggle } from "@/components/ui/toggle";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { COLOUR_CLASS, COLOURS, dayRange, longDate } from "@/lib/company/holidays";
import { cn } from "@/lib/utils";

import { FormSheet } from "./form-sheet";

type Page = components["schemas"]["HolidayManagement"];
type Closure = components["schemas"]["CompanyHolidayOut"];
type Kind = components["schemas"]["HolidayTypeOut"];

const REGION_NAMES: Record<Page["region"], string> = {
  "england-and-wales": "England and Wales",
  scotland: "Scotland",
  "northern-ireland": "Northern Ireland",
};

function Dot({ colour }: { colour: Kind["colour"] | null }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "size-3 shrink-0 rounded-full",
        colour ? COLOUR_CLASS[colour] : "bg-fill-secondary",
      )}
    />
  );
}

/** `/holiday-management` (plan 8.6): bank holidays, the company's own closures, and holiday types. */
export function HolidayManagementPage({ page }: { page: Page }) {
  const router = useRouter();
  const can = useCan();
  const mayEdit = can("holiday.calendar.write");
  const mayEditTypes = can("holiday.type.write");
  const [closure, setClosure] = useState<Closure | "new" | null>(null);
  const [kind, setKind] = useState<Kind | "new" | null>(null);
  const types = new Map(page.types.map((item) => [item.id, item]));
  const go = (year: number) => router.push(`/holiday-management?year=${year}`);

  return (
    <>
      <PageHeader
        title="Holidays"
        description="Public holidays, and the days your company is closed."
        actions={
          <div className="flex items-center gap-1">
            <IconButton label="Previous year" variant="gray" onClick={() => go(page.year - 1)}>
              <Icon icon={ChevronLeft} />
            </IconButton>
            <p
              className="text-headline text-label min-w-16 text-center tabular-nums"
              aria-live="polite"
            >
              {page.year}
            </p>
            <IconButton label="Next year" variant="gray" onClick={() => go(page.year + 1)}>
              <Icon icon={ChevronRight} />
            </IconButton>
          </div>
        }
      />
      <div className="flex flex-col gap-8">
        <GroupedList
          heading="Company closures"
          description="Days the whole company is shut, such as a Christmas shutdown."
        >
          {page.company_holidays.map((item) => (
            <GroupedRow
              key={item.id}
              title={item.name}
              icon={
                <Dot
                  colour={
                    item.holiday_type_id ? (types.get(item.holiday_type_id)?.colour ?? null) : null
                  }
                />
              }
              detail={dayRange(item.start_date, item.end_date)}
              {...(mayEdit ? { onClick: () => setClosure(item) } : {})}
            />
          ))}
          {page.company_holidays.length === 0 ? (
            <GroupedEmpty
              {...(mayEdit
                ? {
                    action: (
                      <Button variant="gray" size="sm" onClick={() => setClosure("new")}>
                        Add closure
                      </Button>
                    ),
                  }
                : {})}
            >
              No closures in {page.year}
            </GroupedEmpty>
          ) : mayEdit ? (
            <GroupedEmpty
              action={
                <Button variant="gray" size="sm" onClick={() => setClosure("new")}>
                  Add closure
                </Button>
              }
            >
              Add another
            </GroupedEmpty>
          ) : null}
        </GroupedList>

        <GroupedList heading="Holiday types" description="Labels and colours for your closures.">
          {page.types.map((item) => (
            <GroupedRow
              key={item.id}
              title={item.name}
              icon={<Dot colour={item.colour} />}
              {...(mayEditTypes ? { onClick: () => setKind(item) } : {})}
            />
          ))}
          {page.types.length === 0 ? (
            <GroupedEmpty
              {...(mayEditTypes
                ? {
                    action: (
                      <Button variant="gray" size="sm" onClick={() => setKind("new")}>
                        Add type
                      </Button>
                    ),
                  }
                : {})}
            >
              No holiday types yet
            </GroupedEmpty>
          ) : mayEditTypes ? (
            <GroupedEmpty
              action={
                <Button variant="gray" size="sm" onClick={() => setKind("new")}>
                  Add type
                </Button>
              }
            >
              Add another
            </GroupedEmpty>
          ) : null}
        </GroupedList>

        <GroupedList
          heading={`Bank holidays, ${REGION_NAMES[page.region]}`}
          description={
            page.bank_holidays_updated_at
              ? `From GOV.UK, last updated ${longDate(page.bank_holidays_updated_at.slice(0, 10))}. They refresh every week.`
              : "From GOV.UK. They have not been loaded yet; they arrive with the next weekly update."
          }
        >
          {page.bank_holidays.map((item) => (
            <GroupedRow
              key={item.on_date}
              title={item.title}
              icon={<Icon icon={CalendarDays} />}
              detail={longDate(item.on_date)}
            />
          ))}
          {page.bank_holidays.length === 0 ? (
            <GroupedEmpty>Nothing listed for {page.year}</GroupedEmpty>
          ) : null}
        </GroupedList>
      </div>

      {closure ? (
        <ClosureSheet
          key={closure === "new" ? "new" : closure.id}
          closure={closure === "new" ? null : closure}
          types={page.types}
          year={page.year}
          onClose={() => setClosure(null)}
        />
      ) : null}
      {kind ? (
        <TypeSheet
          key={kind === "new" ? "new" : kind.id}
          kind={kind === "new" ? null : kind}
          onClose={() => setKind(null)}
        />
      ) : null}
    </>
  );
}

function ClosureSheet({
  closure,
  types,
  year,
  onClose,
}: {
  closure: Closure | null;
  types: Kind[];
  year: number;
  onClose: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [name, setName] = useState(closure?.name ?? "");
  const [start, setStart] = useState<string | null>(closure?.start_date ?? null);
  const [end, setEnd] = useState<string | null>(closure?.end_date ?? null);
  const [typeId, setTypeId] = useState(closure?.holiday_type_id ?? "");
  const [description, setDescription] = useState(closure?.description ?? "");
  const [deduct, setDeduct] = useState(closure?.deduct_from_annual_leave ?? false);
  const [errors, setErrors] = useState<Partial<Record<"name" | "start_date" | "end_date", string>>>(
    {},
  );
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    const found: typeof errors = {
      ...(name.trim() ? {} : { name: "Give the closure a name." }),
      ...(start ? {} : { start_date: "Choose the first day." }),
      ...(end ? {} : { end_date: "Choose the last day." }),
      ...(start && end && end < start
        ? { end_date: "The last day cannot be before the first day." }
        : {}),
    };
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0 || !start || !end) return;
    const body = {
      name,
      start_date: start,
      end_date: end,
      holiday_type_id: typeId || null,
      description: description.trim() || null,
      deduct_from_annual_leave: deduct,
    };
    setBusy(true);
    const outcome = await attempt((client) =>
      closure
        ? client.PATCH("/company-holidays/{holiday_id}", {
            params: { path: { holiday_id: closure.id } },
            body,
          })
        : client.POST("/company-holidays", { body }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: closure ? "Closure saved" : "Closure added", tone: "success" });
      router.refresh();
      onClose();
      return;
    }
    const { field, message } = outcome.problem;
    if (field === "name" || field === "start_date" || field === "end_date")
      setErrors({ [field]: message });
    else setProblem(outcome.problem);
  }

  async function remove() {
    if (!closure) return;
    const outcome = await attempt((client) =>
      client.DELETE("/company-holidays/{holiday_id}", {
        params: { path: { holiday_id: closure.id } },
      }),
    );
    if (outcome.ok) {
      toast.show({ title: "Closure removed", tone: "success" });
      router.refresh();
      onClose();
    } else setProblem(outcome.problem);
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={closure ? "Edit closure" : "Add closure"}
      description="One entry for each shutdown, from the first day to the last."
      onSubmit={save}
      busy={busy}
      problem={problem}
      {...(closure
        ? {
            archive: {
              label: "Remove",
              question: `Remove ${closure.name}?`,
              detail: "It stops showing on the calendar.",
              onConfirm: remove,
            },
          }
        : {})}
    >
      <TextField
        label="Name"
        name="name"
        autoFocus
        maxLength={120}
        value={name}
        onChange={(event) => setName(event.target.value)}
        error={errors.name}
        hint="For example Christmas shutdown."
      />
      <DatePicker
        label="First day"
        name="start_date"
        value={start}
        onChange={setStart}
        error={errors.start_date}
        {...(year ? { min: `${year - 1}-01-01`, max: `${year + 2}-12-31` } : {})}
      />
      <DatePicker
        label="Last day"
        name="end_date"
        value={end}
        onChange={setEnd}
        error={errors.end_date}
        {...(start ? { min: start } : {})}
      />
      <Select
        label="Type (optional)"
        name="holiday_type_id"
        placeholder="No type"
        value={typeId}
        onChange={(event) => setTypeId(event.target.value)}
      >
        {types.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </Select>
      <TextArea
        label="Description (optional)"
        name="description"
        rows={3}
        maxLength={1000}
        value={description}
        onChange={(event) => setDescription(event.target.value)}
      />
      <Toggle
        label="Take these days from annual leave"
        description="Everyone's annual leave goes down by the working days in this closure."
        checked={deduct}
        onCheckedChange={setDeduct}
      />
    </FormSheet>
  );
}

function TypeSheet({ kind, onClose }: { kind: Kind | null; onClose: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const [name, setName] = useState(kind?.name ?? "");
  const [colour, setColour] = useState<Kind["colour"]>(kind?.colour ?? "blue");
  const [error, setError] = useState<string | undefined>();
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Give the type a name.");
      return;
    }
    setError(undefined);
    setProblem(null);
    setBusy(true);
    const outcome = await attempt((client) =>
      kind
        ? client.PATCH("/holiday-types/{type_id}", {
            params: { path: { type_id: kind.id } },
            body: { name, colour },
          })
        : client.POST("/holiday-types", { body: { name, colour } }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: kind ? "Type saved" : "Type added", tone: "success" });
      router.refresh();
      onClose();
    } else if (outcome.problem.field === "name") setError(outcome.problem.message);
    else setProblem(outcome.problem);
  }

  async function archive() {
    if (!kind) return;
    const outcome = await attempt((client) =>
      client.DELETE("/holiday-types/{type_id}", { params: { path: { type_id: kind.id } } }),
    );
    if (outcome.ok) {
      toast.show({ title: "Type archived", tone: "success" });
      router.refresh();
      onClose();
    } else setProblem(outcome.problem);
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={kind ? "Edit holiday type" : "Add holiday type"}
      onSubmit={save}
      busy={busy}
      problem={problem}
      {...(kind
        ? {
            archive: {
              label: "Archive",
              question: `Archive ${kind.name}?`,
              detail: "Closures that use it must be changed or removed first.",
              onConfirm: archive,
            },
          }
        : {})}
    >
      <TextField
        label="Name"
        name="name"
        autoFocus
        maxLength={80}
        value={name}
        onChange={(event) => setName(event.target.value)}
        error={error}
      />
      <fieldset className="flex flex-col gap-2">
        <legend className="text-callout text-label mb-1">Colour</legend>
        <div role="radiogroup" aria-label="Colour" className="flex flex-wrap gap-2">
          {COLOURS.map((option) => (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={colour === option.value}
              aria-label={option.label}
              onClick={() => setColour(option.value)}
              className={cn(
                "hit-target flex items-center gap-2 rounded-pill px-3 py-1.5 text-callout outline-none",
                "focus-visible:outline-accent focus-visible:outline-2 focus-visible:outline-offset-2",
                colour === option.value
                  ? "bg-fill-secondary text-label font-semibold ring-accent ring-2"
                  : "text-label",
              )}
            >
              <Dot colour={option.value} />
              {option.label}
            </button>
          ))}
        </div>
      </fieldset>
    </FormSheet>
  );
}
