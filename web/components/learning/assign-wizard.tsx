"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

type Course = components["schemas"]["CourseCardOut"];
type Department = components["schemas"]["DepartmentOut"];
type Person = components["schemas"]["EmployeeRow"];
type Scope = "everyone" | "departments" | "named";

const SCOPES: { value: Scope; label: string; hint: string }[] = [
  { value: "everyone", label: "Everyone", hint: "Every current member of staff." },
  { value: "departments", label: "Departments", hint: "Everyone in the departments you choose." },
  { value: "named", label: "Named people", hint: "Only the people you choose." },
];

function toggle(set: Set<string>, id: string): Set<string> {
  const next = new Set(set);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/** Three steps: the courses, the people, then one due date and a review. Nothing is saved until the
 * last step, and the server checks every person before it writes a row. */
export function AssignWizard({
  open,
  onOpenChange,
  courses,
  departments,
  initialCourse,
  onAssigned,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  courses: Course[];
  departments: Department[];
  initialCourse: string | null;
  onAssigned: () => void;
}) {
  // The parent remounts this component each time it opens, so the state starts fresh every time.
  const [step, setStep] = useState(1);
  const [courseIds, setCourseIds] = useState<Set<string>>(
    () => new Set(initialCourse ? [initialCourse] : []),
  );
  const [scope, setScope] = useState<Scope>("everyone");
  const [departmentIds, setDepartmentIds] = useState<Set<string>>(new Set());
  const [employeeIds, setEmployeeIds] = useState<Set<string>>(new Set());
  const [people, setPeople] = useState<Person[]>([]);
  const [dueOn, setDueOn] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    if (!open || scope !== "named" || people.length > 0) return;
    let active = true;
    void attempt((c) => c.GET("/employees", { params: { query: { archived: false } } })).then(
      (r) => {
        if (active && r.ok) setPeople(r.data.employees);
      },
    );
    return () => {
      active = false;
    };
  }, [open, scope, people.length]);

  const chosenCourses = courses.filter((course) => courseIds.has(course.id));

  function canContinue(): boolean {
    if (step === 1) return courseIds.size > 0;
    if (step === 2) {
      if (scope === "departments") return departmentIds.size > 0;
      if (scope === "named") return employeeIds.size > 0;
      return true;
    }
    return dueOn !== "";
  }

  async function assign() {
    setBusy(true);
    setProblem(null);
    const outcome = await attempt((c) =>
      c.POST("/learning/assignments", {
        body: {
          course_ids: [...courseIds],
          scope,
          department_ids: scope === "departments" ? [...departmentIds] : [],
          employee_ids: scope === "named" ? [...employeeIds] : [],
          due_on: dueOn,
        },
      }),
    );
    setBusy(false);
    if (!outcome.ok) {
      setProblem(outcome.problem);
      return;
    }
    const { created, already_assigned: already } = outcome.data;
    setResult(
      `${created} new ${created === 1 ? "assignment" : "assignments"} made. ${already} ${already === 1 ? "was" : "were"} already there, so nothing changed for ${already === 1 ? "it" : "them"}.`,
    );
    onAssigned();
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        title="Assign courses"
        description={result ? "Done" : `Step ${step} of 3`}
        side="right"
        footer={
          result ? (
            <Button variant="filled" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          ) : (
            <div className="flex w-full justify-between gap-3">
              <Button
                variant="gray"
                disabled={step === 1 || busy}
                onClick={() => setStep((s) => s - 1)}
              >
                Back
              </Button>
              {step < 3 ? (
                <Button
                  variant="filled"
                  disabled={!canContinue() || busy}
                  onClick={() => setStep((s) => s + 1)}
                >
                  Continue
                </Button>
              ) : (
                <Button
                  variant="filled"
                  disabled={!canContinue() || busy}
                  onClick={() => void assign()}
                >
                  Assign
                </Button>
              )}
            </div>
          )
        }
      >
        <div className="flex flex-col gap-5">
          {problem ? <Alert tone="danger" title={problem.message} /> : null}
          {result ? <Alert tone="success" title={result} /> : null}

          {!result && step === 1 ? (
            <fieldset className="flex flex-col gap-3">
              <legend className="text-callout text-label mb-1 font-semibold">Choose courses</legend>
              {courses.map((course) => (
                <Checkbox
                  key={course.id}
                  label={course.title}
                  description={`${course.duration_minutes} minutes · ${course.section_count} sections`}
                  checked={courseIds.has(course.id)}
                  onCheckedChange={() => setCourseIds((set) => toggle(set, course.id))}
                />
              ))}
            </fieldset>
          ) : null}

          {!result && step === 2 ? (
            <fieldset className="flex flex-col gap-3">
              <legend className="text-callout text-label mb-1 font-semibold">
                Who should take them?
              </legend>
              {SCOPES.map((option) => (
                <label key={option.value} className="flex items-start gap-3">
                  <input
                    type="radio"
                    name="scope"
                    value={option.value}
                    checked={scope === option.value}
                    onChange={() => setScope(option.value)}
                    className="mt-1 size-4"
                  />
                  <span className="flex flex-col">
                    <span className="text-body text-label">{option.label}</span>
                    <span className="text-footnote text-label-secondary">{option.hint}</span>
                  </span>
                </label>
              ))}
              {scope === "departments" ? (
                <div className="flex flex-col gap-2 pl-7">
                  {departments.map((department) => (
                    <Checkbox
                      key={department.id}
                      label={department.name}
                      checked={departmentIds.has(department.id)}
                      onCheckedChange={() => setDepartmentIds((set) => toggle(set, department.id))}
                    />
                  ))}
                </div>
              ) : null}
              {scope === "named" ? (
                <div className="flex max-h-72 flex-col gap-2 overflow-y-auto pl-7">
                  {people.map((person) => (
                    <Checkbox
                      key={person.id}
                      label={`${person.first_name} ${person.last_name}`}
                      checked={employeeIds.has(person.id)}
                      onCheckedChange={() => setEmployeeIds((set) => toggle(set, person.id))}
                    />
                  ))}
                </div>
              ) : null}
            </fieldset>
          ) : null}

          {!result && step === 3 ? (
            <div className="flex flex-col gap-4">
              <TextField
                label="Due on"
                type="date"
                value={dueOn}
                onChange={(event) => setDueOn(event.target.value)}
              />
              <div className="bg-elevated border-separator rounded-card flex flex-col gap-2 border p-4">
                <p className="text-callout text-label font-semibold">Review</p>
                <p className="text-body text-label-secondary">
                  {chosenCourses.map((course) => course.title).join(", ") || "No course chosen"}
                </p>
                <p className="text-body text-label-secondary">
                  {scope === "everyone"
                    ? "Everyone in the company"
                    : scope === "departments"
                      ? `${departmentIds.size} department(s)`
                      : `${employeeIds.size} named person(s)`}
                </p>
                <p className="text-footnote text-label-secondary">
                  Anyone already assigned a course keeps their existing assignment.
                </p>
              </div>
            </div>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
