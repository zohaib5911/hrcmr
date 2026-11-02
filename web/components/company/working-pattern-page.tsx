"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { NumberField } from "@/components/ui/number-field";
import { Toggle } from "@/components/ui/toggle";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { WEEKDAYS, weekSummary } from "@/lib/company/working-pattern";

type Pattern = components["schemas"]["WorkingPattern-Output"];

/** `/company/working-pattern` (plan 8.6): which days the company normally works, and for how long. */
export function WorkingPatternPage({ pattern }: { pattern: Pattern }) {
  const router = useRouter();
  const toast = useToast();
  const can = useCan();
  const mayEdit = can("holiday.calendar.write");
  const [days, setDays] = useState(
    pattern.days.map((day) => ({ ...day, hours: Number(day.hours) })),
  );
  const [bank, setBank] = useState(pattern.bank_holidays_non_working);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  function change(weekday: number, patch: Partial<{ is_working: boolean; hours: number }>) {
    setDays((current) =>
      current.map((day) => (day.weekday === weekday ? { ...day, ...patch } : day)),
    );
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    setBusy(true);
    const outcome = await attempt((client) =>
      client.PUT("/working-pattern", {
        body: {
          days: days.map((day) => ({
            weekday: day.weekday,
            is_working: day.is_working,
            hours: day.is_working ? day.hours.toFixed(2) : "0",
          })),
          bank_holidays_non_working: bank,
        },
      }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: "Working pattern saved", tone: "success" });
      router.refresh();
    } else setProblem(outcome.problem);
  }

  return (
    <>
      <PageHeader
        title="Working pattern"
        description={`Your normal week: ${weekSummary(days)}. Leave and attendance use it.`}
        actions={
          <Button asChild variant="gray">
            <Link href="/holiday-management">Holidays</Link>
          </Button>
        }
      />
      <form onSubmit={save} noValidate className="flex max-w-2xl flex-col gap-6">
        {problem ? <Alert tone="danger" title={problem.message} /> : null}
        <ul className="bg-elevated rounded-card shadow-e1 divide-separator divide-y overflow-hidden">
          {days.map((day) => (
            <li key={day.weekday} className="flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
              <div className="min-w-40 flex-1">
                <Toggle
                  label={WEEKDAYS[day.weekday - 1] ?? ""}
                  checked={day.is_working}
                  disabled={!mayEdit}
                  onCheckedChange={(checked) =>
                    change(day.weekday, {
                      is_working: checked,
                      hours: checked ? day.hours || 8 : 0,
                    })
                  }
                />
              </div>
              <NumberField
                label={`${WEEKDAYS[day.weekday - 1]} hours`}
                unit="hours"
                min={0}
                max={24}
                step={0.5}
                containerClassName="w-36"
                value={day.is_working ? day.hours : null}
                disabled={!mayEdit || !day.is_working}
                onChange={(value) => change(day.weekday, { hours: value ?? 0 })}
              />
            </li>
          ))}
        </ul>
        <Toggle
          label="Bank holidays are not working days"
          description="Turn off if your people normally work on bank holidays."
          checked={bank}
          disabled={!mayEdit}
          onCheckedChange={setBank}
        />
        {mayEdit ? (
          <div className="flex justify-end">
            <Button type="submit" loading={busy}>
              Save
            </Button>
          </div>
        ) : null}
      </form>
    </>
  );
}
