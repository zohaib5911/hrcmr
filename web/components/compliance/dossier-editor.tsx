"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/app/page-header";
import { FormSheet } from "@/components/company/form-sheet";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DatePicker } from "@/components/ui/date-picker";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { DOSSIER_SECTIONS, type DossierLink } from "@/lib/compliance/hub";
import { shortDate } from "@/lib/employees/profile";

type Form = components["schemas"]["DossierLinkIn"];

export function DossierEditor({ links }: { links: DossierLink[] }) {
  const [editing, setEditing] = useState<DossierLink | "new" | null>(null);
  const router = useRouter();
  return (
    <>
      <PageHeader
        title="Dossier links"
        description="Official guidance shown to every company's Sponsor Management Dossier."
        actions={<Button onClick={() => setEditing("new")}>Add link</Button>}
      />
      <ul className="bg-elevated rounded-card shadow-e1 divide-separator divide-y">
        {links.map((link) => (
          <li key={link.id} className="flex flex-wrap items-center gap-3 p-4">
            <div className="min-w-0 flex-1">
              <p className="text-body text-label break-words">{link.title}</p>
              <p className="text-caption text-label-secondary">
                {DOSSIER_SECTIONS.find(([value]) => value === link.section)?.[1]} · checked{" "}
                {shortDate(link.checked_on)} · position {link.position}
              </p>
            </div>
            <StatusChip tone={link.active ? "success" : "neutral"}>
              {link.active ? "Published" : "Hidden"}
            </StatusChip>
            <Button variant="gray" onClick={() => setEditing(link)}>
              Edit<span className="sr-only"> {link.title}</span>
            </Button>
          </li>
        ))}
      </ul>
      {editing && (
        <LinkSheet
          record={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            router.refresh();
          }}
        />
      )}
    </>
  );
}

function LinkSheet({
  record,
  onClose,
  onSaved,
}: {
  record: DossierLink | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<Form>(
    record
      ? {
          section: record.section,
          title: record.title,
          url: record.url,
          checked_on: record.checked_on,
          position: record.position,
          active: record.active,
        }
      : {
          section: "licence",
          title: "",
          url: "https://www.gov.uk/",
          checked_on: new Date().toISOString().slice(0, 10),
          position: 0,
          active: true,
        },
  );
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const toast = useToast();
  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      record
        ? c.PUT("/admin/dossier-links/{link_id}", {
            params: { path: { link_id: record.id } },
            body: form,
          })
        : c.POST("/admin/dossier-links", { body: form }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    toast.show({ title: "Dossier link saved", tone: "success" });
    onSaved();
  }
  return (
    <FormSheet
      open
      title={record ? "Edit dossier link" : "Add dossier link"}
      onOpenChange={(open) => !open && onClose()}
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      <Select
        label="Group"
        value={form.section}
        onChange={(e) => set("section", e.target.value as Form["section"])}
      >
        {DOSSIER_SECTIONS.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </Select>
      <TextField
        label="Link title"
        value={form.title}
        onChange={(e) => set("title", e.target.value)}
        maxLength={160}
        required
      />
      <TextField
        label="Official GOV.UK URL"
        type="url"
        value={form.url}
        onChange={(e) => set("url", e.target.value)}
        hint="Full https://www.gov.uk/ address. Open the official page to verify it before saving."
        maxLength={1000}
        required
      />
      <DatePicker
        label="Date checked"
        value={form.checked_on}
        onChange={(value) => set("checked_on", value ?? "")}
        max={new Date().toISOString().slice(0, 10)}
        required
      />
      <TextField
        label="Position"
        type="number"
        value={form.position}
        onChange={(e) => set("position", Number(e.target.value))}
        min={0}
        max={10000}
        required
      />
      <Checkbox
        label="Publish in the dossier"
        checked={form.active}
        onCheckedChange={(checked) => set("active", checked === true)}
      />
    </FormSheet>
  );
}
