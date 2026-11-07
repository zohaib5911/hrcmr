"use client";

import { useEffect, useState, type FormEvent } from "react";

import { useCan } from "@/components/app/session-context";
import { FormSheet } from "@/components/company/form-sheet";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

export type Requisition = components["schemas"]["RequisitionOut"];
type Status = Requisition["status"];
type Per = NonNullable<Requisition["budget_per"]>;

const STATUS_LABELS: Record<Status, string> = {
  draft: "Draft",
  open: "Open (needs approval)",
  on_hold: "On hold",
  filled: "Filled",
  cancelled: "Cancelled",
};
const PER_LABELS: Record<Per, string> = { year: "Per year", month: "Per month", hour: "Per hour" };

function fieldError(problem: Problem | null, field: string): string | undefined {
  return problem?.field === field ? problem.message : undefined;
}

/**
 * One requisition: its details, and its status. Only someone allowed to approve can set Open; the
 * Cancel button asks first, and a cancelled requisition cannot change.
 */
export function RequisitionSheet({
  item,
  onOpenChange,
  onSaved,
}: {
  item: Requisition | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const can = useCan();
  const toast = useToast();
  const mayApprove = can("recruitment.requisition.approve");
  const locked = item?.status === "cancelled";
  const [title, setTitle] = useState(item?.job_title ?? "");
  const [department, setDepartment] = useState(item?.department_id ?? "");
  const [headcount, setHeadcount] = useState(String(item?.headcount ?? 1));
  const [grade, setGrade] = useState(item?.grade ?? "");
  const [from, setFrom] = useState(item?.budget_from ?? "");
  const [to, setTo] = useState(item?.budget_to ?? "");
  const [per, setPer] = useState<Per | "">(item?.budget_per ?? "");
  const [justification, setJustification] = useState(item?.justification ?? "");
  const [status, setStatus] = useState<Status>(item?.status ?? "draft");
  const [departments, setDepartments] = useState<{ id: string; name: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    let active = true;
    void attempt((c) => c.GET("/departments")).then((result) => {
      if (active && result.ok)
        setDepartments(result.data.map((row) => ({ id: row.id, name: row.name })));
    });
    return () => {
      active = false;
    };
  }, []);

  function body() {
    return {
      job_title: title.trim(),
      department_id: department || null,
      headcount: Number(headcount),
      grade: grade.trim() || null,
      budget_from: from === "" ? null : String(from),
      budget_to: to === "" ? null : String(to),
      budget_per: per || null,
      justification: justification.trim() || null,
    };
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!title.trim())
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Enter the job title.",
        field: "job_title",
      } as Problem);
    setBusy(true);
    const saved = item
      ? await attempt((c) =>
          c.PATCH("/requisitions/{requisition_id}", {
            params: { path: { requisition_id: item.id } },
            body: body(),
          }),
        )
      : await attempt((c) => c.POST("/requisitions", { body: body() }));
    if (!saved.ok) {
      setBusy(false);
      return setProblem(saved.problem);
    }
    if (item && status !== item.status) {
      const changed = await attempt((c) =>
        c.PATCH("/requisitions/{requisition_id}/status", {
          params: { path: { requisition_id: saved.data.id } },
          body: { status },
        }),
      );
      setBusy(false);
      if (!changed.ok) return setProblem(changed.problem);
    } else setBusy(false);
    toast.show({ title: item ? "Requisition saved" : "Requisition created", tone: "success" });
    onSaved();
  }

  async function cancel() {
    if (!item) return;
    setBusy(true);
    const result = await attempt((c) =>
      c.PATCH("/requisitions/{requisition_id}/status", {
        params: { path: { requisition_id: item.id } },
        body: { status: "cancelled" },
      }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: "Requisition cancelled", tone: "success" });
      onSaved();
    } else setProblem(result.problem);
  }

  return (
    <FormSheet
      open
      title={item ? "Requisition" : "New requisition"}
      description={
        locked
          ? "This requisition is cancelled and can no longer change."
          : "Describe the role. It must be approved before it can open."
      }
      onOpenChange={onOpenChange}
      onSubmit={(event) => void save(event)}
      busy={busy}
      problem={problem}
      saveLabel={item ? "Save changes" : "Create requisition"}
    >
      <fieldset disabled={busy || locked} className="flex min-w-0 flex-col gap-4">
        <TextField
          label="Job title"
          required
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          error={fieldError(problem, "job_title")}
        />
        <Select
          label="Department"
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
          error={fieldError(problem, "department_id")}
        >
          <option value="">No department</option>
          {departments.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </Select>
        <TextField
          label="Headcount"
          type="number"
          min={1}
          max={999}
          required
          value={headcount}
          onChange={(e) => setHeadcount(e.target.value)}
        />
        <TextField
          label="Grade (optional)"
          maxLength={40}
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Budget from (optional)"
            type="number"
            min={0}
            step="0.01"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            error={fieldError(problem, "budget_from")}
          />
          <TextField
            label="Budget to (optional)"
            type="number"
            min={0}
            step="0.01"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            error={fieldError(problem, "budget_to")}
          />
        </div>
        <Select label="Budget is" value={per} onChange={(e) => setPer(e.target.value as Per | "")}>
          <option value="">Not stated</option>
          {(Object.keys(PER_LABELS) as Per[]).map((value) => (
            <option key={value} value={value}>
              {PER_LABELS[value]}
            </option>
          ))}
        </Select>
        <TextArea
          label="Justification (optional)"
          rows={4}
          maxLength={5000}
          value={justification}
          onChange={(e) => setJustification(e.target.value)}
        />
        {item && (
          <Select
            label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value as Status)}
            hint={
              mayApprove ? undefined : "Only someone allowed to approve can open a requisition."
            }
          >
            {(["draft", "open", "on_hold", "filled"] as Status[]).map((value) => (
              <option
                key={value}
                value={value}
                disabled={value === "open" && !mayApprove && item.status !== "open"}
              >
                {STATUS_LABELS[value]}
              </option>
            ))}
          </Select>
        )}
        {item?.approved_at && (
          <p className="text-callout text-label-secondary">
            Approved {item.approved_at.slice(0, 10)}
            {item.approved_by_name ? ` by ${item.approved_by_name}` : ""}
          </p>
        )}
        {item && !locked && (
          <ConfirmDialog
            trigger={
              <Button type="button" variant="plain" disabled={busy}>
                Cancel requisition
              </Button>
            }
            title="Cancel this requisition?"
            description="A cancelled requisition cannot change and cannot open. Create a new one if the role comes back."
            confirmLabel="Cancel requisition"
            destructive
            onConfirm={cancel}
          />
        )}
        {problem && !problem.field && <Alert tone="danger" title={problem.message} />}
      </fieldset>
    </FormSheet>
  );
}
