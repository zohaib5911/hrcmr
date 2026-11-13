"use client";

import { Building2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { Icon } from "@/components/ui/icon";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

import { FormSheet } from "./form-sheet";

type Department = components["schemas"]["DepartmentOut"];

/** `/company/departments` (plan 8.15): the parts of the company, which job titles sit in. */
export function DepartmentsPage({ departments }: { departments: Department[] }) {
  const can = useCan();
  const mayEdit = can("company.department.write");
  const [editing, setEditing] = useState<Department | "new" | null>(null);

  return (
    <>
      <PageHeader
        title="Departments"
        description="The parts of your company. Job titles are grouped under them."
        actions={
          mayEdit && departments.length > 0 ? (
            <Button onClick={() => setEditing("new")}>Add department</Button>
          ) : null
        }
      />
      {departments.length === 0 ? (
        <div className="bg-elevated rounded-card shadow-e1">
          <EmptyState
            icon={Building2}
            title="No departments yet"
            description="Add the teams or sections you have, such as Care, Kitchen or Finance."
            {...(mayEdit
              ? { action: <Button onClick={() => setEditing("new")}>Add department</Button> }
              : {})}
          />
        </div>
      ) : (
        <GroupedList heading="Your departments">
          {departments.map((department) => (
            <GroupedRow
              key={department.id}
              title={department.name}
              icon={<Icon icon={Building2} />}
              detail={`${department.designations} ${department.designations === 1 ? "job title" : "job titles"}`}
              {...(mayEdit ? { onClick: () => setEditing(department) } : {})}
            />
          ))}
        </GroupedList>
      )}
      {editing ? (
        <DepartmentSheet
          key={editing === "new" ? "new" : editing.id}
          department={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </>
  );
}

function DepartmentSheet({
  department,
  onClose,
}: {
  department: Department | null;
  onClose: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [name, setName] = useState(department?.name ?? "");
  const [error, setError] = useState<string | undefined>();
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Give the department a name.");
      return;
    }
    setError(undefined);
    setProblem(null);
    setBusy(true);
    const outcome = await attempt((client) =>
      department
        ? client.PATCH("/departments/{department_id}", {
            params: { path: { department_id: department.id } },
            body: { name },
          })
        : client.POST("/departments", { body: { name } }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: department ? "Department saved" : "Department added", tone: "success" });
      router.refresh();
      onClose();
    } else if (outcome.problem.field === "name") setError(outcome.problem.message);
    else setProblem(outcome.problem);
  }

  async function archive() {
    if (!department) return;
    const outcome = await attempt((client) =>
      client.DELETE("/departments/{department_id}", {
        params: { path: { department_id: department.id } },
      }),
    );
    if (outcome.ok) {
      toast.show({ title: "Department archived", tone: "success" });
      router.refresh();
      onClose();
    } else setProblem(outcome.problem);
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={department ? "Rename department" : "Add department"}
      onSubmit={save}
      busy={busy}
      problem={problem}
      {...(department
        ? {
            archive: {
              label: "Archive",
              question: `Archive ${department.name}?`,
              detail: "It stops appearing in lists. Archive or move its job titles first.",
              onConfirm: archive,
            },
          }
        : {})}
    >
      <TextField
        label="Name"
        name="name"
        autoFocus
        maxLength={100}
        value={name}
        onChange={(event) => setName(event.target.value)}
        error={error}
      />
    </FormSheet>
  );
}
