"use client";

import { ExternalLink } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { attempt, type Problem } from "@/lib/auth/request";
import {
  EMPTY_EMPLOYEE,
  latestHireDate,
  newEmployeeProblems,
  type NewEmployee,
} from "@/lib/employees/new";

const today = () => new Date().toISOString().slice(0, 10);

/** `/employees/new` (plan 8.3): the essentials only; everything else is added on the profile. */
export function NewEmployeePage() {
  const router = useRouter();
  const toast = useToast();
  const [values, setValues] = useState<NewEmployee>(EMPTY_EMPLOYEE);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof NewEmployee>(key: K, value: NewEmployee[K]) =>
    setValues((current) => ({ ...current, [key]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const found = newEmployeeProblems(values, today());
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0 || !values.hireDate) return;
    setBusy(true);
    const outcome = await attempt((api) =>
      api.POST("/employees", {
        body: {
          first_name: values.firstName.trim(),
          last_name: values.lastName.trim(),
          email: values.email.trim(),
          phone: values.phone.trim() || null,
          employee_number: values.employeeNumber.trim(),
          hire_date: values.hireDate as string,
          status: values.status,
        },
      }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({
        title: `${values.firstName.trim()} ${values.lastName.trim()} added`,
        tone: "success",
      });
      router.push("/employees");
      router.refresh();
    } else if (outcome.problem.field) {
      setErrors({ [outcome.problem.field]: outcome.problem.message });
    } else setProblem(outcome.problem);
  }

  return (
    <>
      <PageHeader
        title="New employee"
        description="Start with the essentials. You can add everything else on their profile."
      />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <form
          onSubmit={submit}
          noValidate
          className="bg-elevated rounded-card shadow-e1 flex flex-col gap-4 p-5"
        >
          {problem ? <Alert tone="danger" title={problem.message} /> : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="First name"
              value={values.firstName}
              onChange={(e) => set("firstName", e.target.value)}
              error={errors.first_name}
              autoComplete="off"
            />
            <TextField
              label="Last name"
              value={values.lastName}
              onChange={(e) => set("lastName", e.target.value)}
              error={errors.last_name}
              autoComplete="off"
            />
          </div>
          <TextField
            label="Work email"
            type="email"
            value={values.email}
            onChange={(e) => set("email", e.target.value)}
            error={errors.email}
            autoComplete="off"
          />
          <TextField
            label="Contact number (optional)"
            type="tel"
            value={values.phone}
            onChange={(e) => set("phone", e.target.value)}
            autoComplete="off"
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Employee number"
              value={values.employeeNumber}
              onChange={(e) => set("employeeNumber", e.target.value)}
              error={errors.employee_number}
              hint="Each number is used once in your company, ignoring capitals and spaces."
              autoComplete="off"
            />
            <DatePicker
              label="Hire date"
              name="hire_date"
              value={values.hireDate}
              onChange={(value) => set("hireDate", value)}
              max={latestHireDate(today())}
              error={errors.hire_date}
            />
          </div>
          <Select
            label="Status"
            value={values.status}
            onChange={(e) => set("status", e.target.value as NewEmployee["status"])}
          >
            <option value="active">Active</option>
            <option value="on_leave">On leave</option>
          </Select>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="gray" onClick={() => router.push("/employees")}>
              Cancel
            </Button>
            <Button type="submit" loading={busy}>
              Add employee
            </Button>
          </div>
        </form>
        <aside aria-label="New starter checklist" className="text-callout text-label-secondary">
          <h2 className="text-headline text-label">New starter checklist</h2>
          <p className="mt-1">
            Before their first day, make sure you have their right to work evidence, bank details,
            tax information and a signed contract. GOV.UK lists what to do when you take on an
            employee.
          </p>
          <a
            href="https://www.gov.uk/new-employee"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-text mt-2 inline-flex items-center gap-1 underline underline-offset-2"
          >
            GOV.UK: take on an employee
            <ExternalLink aria-hidden="true" className="size-4" />
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        </aside>
      </div>
    </>
  );
}
