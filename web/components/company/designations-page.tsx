"use client";

import { BadgeCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { FindCodeButton } from "@/components/soc/find-code";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { Icon } from "@/components/ui/icon";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

import { FormSheet } from "./form-sheet";

type Designation = components["schemas"]["DesignationOut"];
type Department = components["schemas"]["DepartmentOut"];

/** `/company/designations` (plan 8.15): job titles, each in a department, optionally with a SOC code. */
export function DesignationsPage({
  designations,
  departments,
}: {
  designations: Designation[];
  departments: Department[];
}) {
  const can = useCan();
  const mayEdit = can("settings.designation.write");
  const [editing, setEditing] = useState<Designation | "new" | null>(null);
  const noDepartments = departments.length === 0;
  const groups = Map.groupBy(designations, (item) => item.department_name);

  return (
    <>
      <PageHeader
        title="Designations"
        description="Job titles, each in a department. A SOC code links a title to the sponsorship rules."
        actions={
          mayEdit && !noDepartments ? (
            <Button onClick={() => setEditing("new")}>Add job title</Button>
          ) : null
        }
      />
      {designations.length === 0 ? (
        <div className="bg-elevated rounded-card shadow-e1">
          <EmptyState
            icon={BadgeCheck}
            title="No job titles yet"
            description={
              noDepartments
                ? "Job titles sit in departments, so add a department first."
                : "Add the titles people hold, such as Senior care worker or Head chef."
            }
            action={
              noDepartments ? (
                <Button asChild>
                  <Link href="/company/departments">Add a department</Link>
                </Button>
              ) : mayEdit ? (
                <Button onClick={() => setEditing("new")}>Add job title</Button>
              ) : undefined
            }
          />
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {[...groups].map(([department, items]) => (
            <GroupedList key={department} heading={department}>
              {items.map((item) => (
                <GroupedRow
                  key={item.id}
                  title={item.title}
                  icon={<Icon icon={BadgeCheck} />}
                  {...(item.soc_code ? { detail: `SOC ${item.soc_code}` } : {})}
                  {...(mayEdit ? { onClick: () => setEditing(item) } : {})}
                />
              ))}
            </GroupedList>
          ))}
        </div>
      )}
      {editing ? (
        <DesignationSheet
          key={editing === "new" ? "new" : editing.id}
          designation={editing === "new" ? null : editing}
          departments={departments}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </>
  );
}

function DesignationSheet({
  designation,
  departments,
  onClose,
}: {
  designation: Designation | null;
  departments: Department[];
  onClose: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [title, setTitle] = useState(designation?.title ?? "");
  const [departmentId, setDepartmentId] = useState(
    designation?.department_id ?? departments[0]?.id ?? "",
  );
  const [soc, setSoc] = useState(designation?.soc_code ?? "");
  const [errors, setErrors] = useState<
    Partial<Record<"title" | "department_id" | "soc_code", string>>
  >({});
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    const found: typeof errors = {
      ...(title.trim() ? {} : { title: "Give the job title a name." }),
      ...(departmentId ? {} : { department_id: "Choose a department." }),
      ...(!soc.trim() || /^\d{4}$/.test(soc.trim())
        ? {}
        : { soc_code: "A SOC code is 4 digits, such as 2231." }),
    };
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0) return;
    const body = { title, department_id: departmentId, soc_code: soc.trim() || null };
    setBusy(true);
    const outcome = await attempt((client) =>
      designation
        ? client.PATCH("/designations/{designation_id}", {
            params: { path: { designation_id: designation.id } },
            body,
          })
        : client.POST("/designations", { body }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: designation ? "Job title saved" : "Job title added", tone: "success" });
      router.refresh();
      onClose();
      return;
    }
    const { field, message } = outcome.problem;
    if (field === "title" || field === "department_id" || field === "soc_code") {
      setErrors({ [field]: message });
    } else setProblem(outcome.problem);
  }

  async function archive() {
    if (!designation) return;
    const outcome = await attempt((client) =>
      client.DELETE("/designations/{designation_id}", {
        params: { path: { designation_id: designation.id } },
      }),
    );
    if (outcome.ok) {
      toast.show({ title: "Job title archived", tone: "success" });
      router.refresh();
      onClose();
    } else setProblem(outcome.problem);
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={designation ? "Edit job title" : "Add job title"}
      onSubmit={save}
      busy={busy}
      problem={problem}
      {...(designation
        ? {
            archive: {
              label: "Archive",
              question: `Archive ${designation.title}?`,
              detail: "It stops appearing in lists. People who hold it keep their record.",
              onConfirm: archive,
            },
          }
        : {})}
    >
      <TextField
        label="Job title"
        name="title"
        autoFocus
        maxLength={120}
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        error={errors.title}
      />
      <Select
        label="Department"
        name="department_id"
        value={departmentId}
        onChange={(event) => setDepartmentId(event.target.value)}
        error={errors.department_id}
      >
        {departments.map((department) => (
          <option key={department.id} value={department.id}>
            {department.name}
          </option>
        ))}
      </Select>
      <TextField
        label="SOC code (optional)"
        name="soc_code"
        inputMode="numeric"
        maxLength={4}
        value={soc}
        onChange={(event) => setSoc(event.target.value)}
        error={errors.soc_code}
        hint="Four digits. The Sponsorship checker can find the right one."
      />
      <div>
        <FindCodeButton onFound={setSoc} />
      </div>
    </FormSheet>
  );
}
