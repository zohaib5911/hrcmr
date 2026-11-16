"use client";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { MenuItem } from "@/components/ui/menu";
import { formatUk } from "@/lib/ui/dates";
import type { RotaShift } from "./shift-sheet";
import type { Week, Person, ActionKind, Action } from "./workspace";
import { ActionMenu } from "./action-menu";

export function WeekGrid({
  current,
  days,
  today,
  writable,
  busy,
  ask,
  cell,
  setOpened,
}: {
  current: Week;
  days: string[];
  today: string;
  writable: boolean;
  busy: boolean;
  ask: (kind: ActionKind, title: string, extra?: Partial<Action>) => void;
  cell: (person: Person, day: string) => Promise<void>;
  setOpened: (value: {
    row: RotaShift | null;
    person: Person;
    date: string;
    version: number;
  }) => void;
}) {
  return (
    <div
      className="max-w-full overflow-x-auto rounded-card border border-separator"
      role="region"
      aria-label="Weekly rota"
      tabIndex={0}
    >
      <table className="w-full text-callout text-label">
        <caption className="sr-only">Weekly shift schedule</caption>
        <thead className="bg-elevated">
          <tr>
            <th scope="col" className="min-w-52 p-3 text-left">
              Employee
            </th>
            {days.map((day) => (
              <th
                key={day}
                scope="col"
                className={`min-w-44 p-3 text-left ${day === today ? "bg-accent-tint" : ""}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span>
                    {formatUk(day)}
                    {day === today && <span className="block text-accent-text">Today</span>}
                  </span>
                  {writable && (
                    <ActionMenu label={`Actions for ${formatUk(day)}`} disabled={busy}>
                      <MenuItem
                        onSelect={() =>
                          ask("copy-day", `Copy ${formatUk(day)} to the rest of Mon–Fri?`, {
                            source: day,
                            targets: days.slice(0, 5).filter((d) => d !== day),
                          })
                        }
                      >
                        Copy to the rest of Mon–Fri
                      </MenuItem>
                      <MenuItem
                        onSelect={() =>
                          ask("copy-day", `Copy ${formatUk(day)} to every other day?`, {
                            source: day,
                            targets: days.filter((d) => d !== day),
                          })
                        }
                      >
                        Copy to every other day
                      </MenuItem>
                      <MenuItem
                        destructive
                        onSelect={() => ask("clear", `Clear ${formatUk(day)}?`, { on: day })}
                      >
                        Clear this day
                      </MenuItem>
                    </ActionMenu>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {current.people.map((person) => (
            <tr key={person.id} className="border-t border-separator">
              <th scope="row" className="max-w-64 p-3 text-left align-top">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <Avatar name={person.name} size="sm" decorative />
                    <span className="font-semibold">{person.name}</span>
                    <span className="text-caption text-label-secondary block">
                      {person.employee_number}
                    </span>
                  </div>
                  {person.can_write && (
                    <ActionMenu label={`Actions for ${person.name}`} disabled={busy}>
                      <MenuItem
                        onSelect={() =>
                          ask("copy-employee-week", `Copy ${person.name}'s last week?`, {
                            employee_id: person.id,
                          })
                        }
                      >
                        Copy their last week
                      </MenuItem>
                      <MenuItem
                        destructive
                        onSelect={() =>
                          ask("clear-employee-week", `Clear ${person.name}'s week?`, {
                            employee_id: person.id,
                          })
                        }
                      >
                        Clear their week
                      </MenuItem>
                    </ActionMenu>
                  )}
                </div>
                {current.warnings.some((w) => w.employee_id === person.id) && (
                  <ul className="text-caption text-warning mt-2 flex flex-col gap-1">
                    {[
                      ...new Set(
                        current.warnings
                          .filter((w) => w.employee_id === person.id)
                          .map((w) => w.message),
                      ),
                    ].map((message) => (
                      <li key={message}>{message}</li>
                    ))}
                  </ul>
                )}
              </th>
              {days.map((day) => (
                <td key={day} className={`p-2 align-top ${day === today ? "bg-accent-tint" : ""}`}>
                  <div className="flex flex-col gap-2">
                    {current.shifts
                      .filter((s) => s.employee_id === person.id && s.date === day)
                      .map((shift) => (
                        <Button
                          key={shift.id}
                          variant="gray"
                          className="h-auto min-h-11 flex-col items-start whitespace-normal py-2 text-left"
                          disabled={busy}
                          onClick={() =>
                            setOpened({
                              row: shift,
                              person,
                              date: day,
                              version: current.version,
                            })
                          }
                        >
                          <span>{shift.shift_name ?? "Custom shift"}</span>
                          <span>
                            {shift.starts_local}–{shift.ends_local}
                          </span>
                          <span className="text-caption text-label">{shift.hours}h paid</span>
                        </Button>
                      ))}
                    {person.can_write && (
                      <Button
                        size="sm"
                        variant="plain"
                        disabled={busy}
                        onClick={() => void cell(person, day)}
                        aria-label={`Add shift for ${person.name}, ${formatUk(day)}`}
                      >
                        + Add
                      </Button>
                    )}
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        <tfoot className="bg-elevated">
          <tr>
            <th scope="row" className="p-3 text-left">
              On shift (paid hours)
            </th>
            {days.map((day) => (
              <td key={day} className="p-3">
                {current.totals[day] ?? "0"}
              </td>
            ))}
          </tr>
        </tfoot>
      </table>
      {!current.people.length && <p className="p-4">No employees match this week and search.</p>}
    </div>
  );
}
