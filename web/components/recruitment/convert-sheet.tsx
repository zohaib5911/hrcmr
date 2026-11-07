"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { FormSheet } from "@/components/company/form-sheet";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

type Application = components["schemas"]["ApplicationOut"];

/**
 * Turn the candidate into an employee. Everything comes from the record and the accepted offer; the
 * employee number is the one thing HR types. The server checks both gates again before it converts.
 */
export function ConvertSheet({
  application,
  startDate,
  onOpenChange,
}: {
  application: Application;
  startDate: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [email, setEmail] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [number, setNumber] = useState("");
  const [hireDate, setHireDate] = useState(startDate ?? "");
  const [status, setStatus] = useState<"active" | "on_leave">("active");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/candidates/{candidate_id}", {
        params: { path: { candidate_id: application.candidate_id } },
      }),
    ).then((result) => {
      if (active && result.ok) setEmail(result.data.email);
    });
    return () => {
      active = false;
    };
  }, [application.candidate_id]);

  async function convert(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!number.trim())
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Enter the employee number.",
        field: "employee_number",
      } as Problem);
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/applications/{application_id}/convert", {
        params: { path: { application_id: application.id } },
        body: {
          employee_number: number.trim(),
          hire_date: hireDate || null,
          status,
          phone: phone.trim() || null,
        },
      }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    toast.show({ title: "Candidate is now an employee", tone: "success" });
    router.push(`/employees/${result.data.employee_id}`);
  }

  return (
    <FormSheet
      open
      title="Convert to employee"
      description="The details below come from the candidate and the accepted offer. Choose the employee number to finish."
      onOpenChange={onOpenChange}
      onSubmit={(event) => void convert(event)}
      busy={busy}
      problem={problem}
      saveLabel="Convert to employee"
    >
      <fieldset disabled={busy} className="flex min-w-0 flex-col gap-4">
        <TextField
          label="First name"
          value={application.candidate_name.split(" ")[0] ?? ""}
          readOnly
        />
        <TextField label="Name" value={application.candidate_name} readOnly />
        <TextField
          label="Work email"
          value={email ?? "No email on the candidate record"}
          readOnly
        />
        <TextField
          label="Phone (optional)"
          maxLength={40}
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        <TextField
          label="Employee number"
          required
          maxLength={50}
          value={number}
          onChange={(e) => setNumber(e.target.value)}
          error={problem?.field === "employee_number" ? problem.message : undefined}
        />
        <TextField
          label="Hire date"
          type="date"
          required
          value={hireDate}
          onChange={(e) => setHireDate(e.target.value)}
          hint="Taken from the offer's start date unless you change it."
          error={problem?.field === "hire_date" ? problem.message : undefined}
        />
        <Select
          label="Starts as"
          value={status}
          onChange={(e) => setStatus(e.target.value as "active" | "on_leave")}
        >
          <option value="active">Active</option>
          <option value="on_leave">On leave</option>
        </Select>
      </fieldset>
    </FormSheet>
  );
}
