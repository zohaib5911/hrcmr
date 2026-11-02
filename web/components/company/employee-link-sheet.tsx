"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { FormSheet } from "@/components/company/form-sheet";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/schema";
import { attempt, type Problem } from "@/lib/auth/request";
import type { AccessUser } from "@/lib/company/access";

export function EmployeeLinkSheet({ user, onClose }: { user: AccessUser; onClose: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const [employees, setEmployees] = useState<components["schemas"]["EmployeeRow"][]>([]);
  const [selected, setSelected] = useState(user.employee_id ?? "");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  useEffect(() => {
    let active = true;
    async function load() {
      const result = await attempt((c) =>
        c.GET("/employees", { params: { query: { archived: true } } }),
      );
      if (!active) return;
      setLoading(false);
      if (result.ok) setEmployees(result.data.employees);
      else setProblem(result.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.PUT("/users/{membership_id}/employee", {
        params: { path: { membership_id: user.id } },
        body: { employee_id: selected || null },
      }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: selected ? "Employee linked" : "Employee unlinked", tone: "success" });
      router.refresh();
      onClose();
    } else setProblem(result.problem);
  }
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Link employee"
      description={
        "Choose the employee record for " +
        user.first_name +
        " " +
        user.last_name +
        ". This controls which record they can access through self-service."
      }
      onSubmit={save}
      busy={busy || loading}
      problem={problem}
    >
      <Select
        label="Employee"
        name="employee_id"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
        disabled={loading}
      >
        <option value="">Not linked</option>
        {employees.map((e) => (
          <option
            key={e.id}
            value={e.id}
            disabled={e.status === "archived" && e.id !== user.employee_id}
          >
            {e.first_name} {e.last_name} · {e.employee_number}
            {e.status === "archived" ? " (archived)" : ""}
          </option>
        ))}
      </Select>
    </FormSheet>
  );
}
