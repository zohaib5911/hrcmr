"use client";

import { UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FileDrop, type UploadItem } from "@/components/ui/file-drop";
import { GroupedEmpty, GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { Icon } from "@/components/ui/icon";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { Toggle } from "@/components/ui/toggle";
import { YesNo } from "@/components/ui/yes-no";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

import { FormSheet } from "./form-sheet";

type Person = components["schemas"]["KeyPersonOut"];
type Role = Person["role"];

const ROLES: readonly {
  role: Role;
  title: string;
  about: string;
  many?: boolean;
}[] = [
  {
    role: "authorising_officer",
    title: "Authorising Officer",
    about: "The senior person responsible for the licence and for the company following the rules.",
  },
  {
    role: "key_contact",
    title: "Key Contact",
    about: "The person the Home Office contacts about the licence.",
  },
  {
    role: "level1_user",
    title: "Level 1 User",
    about: "Runs the licence day to day in the Home Office sponsor system.",
  },
  {
    role: "level2_user",
    title: "Level 2 Users",
    about: "Help with tasks in the sponsor system, with fewer permissions than a Level 1 User.",
    many: true,
  },
];

interface Form {
  first_name: string;
  last_name: string;
  designation: string;
  phone: string;
  email: string;
  same_as_authorising_officer: boolean;
  is_settled_or_british: boolean | null;
}

const EMPTY: Form = {
  first_name: "",
  last_name: "",
  designation: "",
  phone: "",
  email: "",
  same_as_authorising_officer: false,
  is_settled_or_british: null,
};

const formOf = (person: Person): Form => ({
  first_name: person.first_name,
  last_name: person.last_name,
  designation: person.designation ?? "",
  phone: person.phone ?? "",
  email: person.email ?? "",
  same_as_authorising_officer: person.same_as_authorising_officer,
  is_settled_or_british: person.is_settled_or_british,
});

const nameOf = (person: Person) => `${person.first_name} ${person.last_name}`;

type Editing = { person: Person; role: Role } | { person: null; role: Role } | null;

/** `/company/key-personnel` (plan 8.15): the four roles the Home Office knows the company by. */
export function KeyPersonnelPage({
  people,
  rolesFilled,
}: {
  people: Person[];
  rolesFilled: number;
}) {
  const can = useCan();
  const mayEdit = can("company.profile.write");
  const [editing, setEditing] = useState<Editing>(null);
  const hasOfficer = people.some((person) => person.role === "authorising_officer");

  return (
    <>
      <PageHeader
        title="Key personnel"
        description={`${rolesFilled} of 4 roles filled. The Home Office expects these people to be on record.`}
      />
      <div className="flex flex-col gap-8">
        {ROLES.map(({ role, title, about, many }) => {
          const here = people.filter((person) => person.role === role);
          const add = mayEdit ? (
            <Button variant="gray" size="sm" onClick={() => setEditing({ person: null, role })}>
              Add
            </Button>
          ) : undefined;
          return (
            <GroupedList key={role} heading={title} description={about}>
              {here.map((person) => (
                <GroupedRow
                  key={person.id}
                  title={nameOf(person)}
                  icon={<Icon icon={UserRound} />}
                  detail={
                    <span className="flex items-center gap-2">
                      {person.has_proof_of_id ? (
                        <StatusChip tone="success">ID on file</StatusChip>
                      ) : null}
                      {person.designation}
                    </span>
                  }
                  {...(mayEdit ? { onClick: () => setEditing({ person, role }) } : {})}
                />
              ))}
              {here.length === 0 ? (
                <GroupedEmpty {...(add ? { action: add } : {})}>Nobody added yet</GroupedEmpty>
              ) : many && mayEdit ? (
                <GroupedEmpty action={add}>Add another</GroupedEmpty>
              ) : null}
            </GroupedList>
          );
        })}
      </div>
      {editing ? (
        <PersonSheet
          key={editing.person?.id ?? `new-${editing.role}`}
          person={editing.person}
          role={editing.role}
          hasOfficer={hasOfficer}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </>
  );
}

function PersonSheet({
  person,
  role,
  hasOfficer,
  onClose,
}: {
  person: Person | null;
  role: Role;
  hasOfficer: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const title = ROLES.find((item) => item.role === role)?.title.replace(/s$/, "") ?? "";
  const [form, setForm] = useState<Form>(person ? formOf(person) : EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof Form, string>>>({});
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<File | null>(null);
  const [proofProblem, setProofProblem] = useState<string | null>(null);
  const set = <K extends keyof Form>(key: K, value: Form[K]) =>
    setForm((current) => ({ ...current, [key]: value }));
  const same = form.same_as_authorising_officer && role !== "authorising_officer";

  async function save(event: FormEvent) {
    event.preventDefault();
    const found: typeof errors = {};
    if (!same) {
      if (!form.first_name.trim()) found.first_name = "Enter a first name.";
      if (!form.last_name.trim()) found.last_name = "Enter a last name.";
    }
    setErrors(found);
    setProblem(null);
    setProofProblem(null);
    if (Object.keys(found).length > 0) return;
    // The officer's own details replace these when the person is the same as the officer.
    const own = same
      ? {}
      : {
          first_name: form.first_name,
          last_name: form.last_name,
          designation: form.designation.trim() || null,
          phone: form.phone.trim() || null,
          email: form.email.trim() || null,
        };
    const details = {
      ...own,
      same_as_authorising_officer: form.same_as_authorising_officer,
      is_settled_or_british: form.is_settled_or_british,
    };
    setBusy(true);
    const saved = await attempt((client) =>
      person
        ? client.PATCH("/key-personnel/{person_id}", {
            params: { path: { person_id: person.id } },
            body: details,
          })
        : client.POST("/key-personnel", { body: { role, ...details } }),
    );
    if (!saved.ok) {
      setBusy(false);
      const { field, message } = saved.problem;
      if (field && field in form) setErrors({ [field]: message });
      else setProblem(saved.problem);
      return;
    }
    if (pending) {
      const body = new FormData();
      body.append("file", pending);
      const sent = await attempt((client) =>
        client.POST("/key-personnel/{person_id}/proof-of-id", {
          params: { path: { person_id: saved.data.id } },
          body: { file: "" },
          bodySerializer: () => body,
        }),
      );
      if (!sent.ok) {
        // The person is saved; only the document was refused. Say so and let them try another.
        setBusy(false);
        router.refresh();
        setPending(null);
        setProofProblem(`Saved, but the document was not accepted: ${sent.problem.message}`);
        return;
      }
    }
    setBusy(false);
    toast.show({ title: person ? "Details saved" : `${title} added`, tone: "success" });
    router.refresh();
    onClose();
  }

  async function remove() {
    if (!person) return;
    const outcome = await attempt((client) =>
      client.DELETE("/key-personnel/{person_id}", { params: { path: { person_id: person.id } } }),
    );
    if (outcome.ok) {
      toast.show({ title: `${title} removed`, tone: "success" });
      router.refresh();
      onClose();
    } else setProblem(outcome.problem);
  }

  async function view() {
    if (!person) return;
    const outcome = await attempt((client) =>
      client.GET("/key-personnel/{person_id}/proof-of-id", {
        params: { path: { person_id: person.id } },
      }),
    );
    if (!outcome.ok) {
      setProblem(outcome.problem);
      return;
    }
    const link = document.createElement("a");
    link.href = outcome.data.url;
    link.rel = "noreferrer";
    link.click();
  }

  async function takeAwayProof() {
    if (!person) return;
    const outcome = await attempt((client) =>
      client.DELETE("/key-personnel/{person_id}/proof-of-id", {
        params: { path: { person_id: person.id } },
      }),
    );
    if (outcome.ok) {
      router.refresh();
      onClose();
    } else setProblem(outcome.problem);
  }

  const items: UploadItem[] = pending
    ? [{ id: pending.name, name: pending.name, size: pending.size, status: "safe" }]
    : [];

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={person ? `Edit ${title}` : `Add ${title}`}
      description="Kept private to your company's managers."
      onSubmit={save}
      busy={busy}
      problem={problem}
      {...(person
        ? {
            archive: {
              label: "Remove",
              question: `Remove ${nameOf(person)} as ${title}?`,
              detail: "Their details stop appearing here. You can add someone else in the role.",
              onConfirm: remove,
            },
          }
        : {})}
    >
      {proofProblem ? <Alert tone="warning" title={proofProblem} /> : null}
      {role !== "authorising_officer" ? (
        <Toggle
          label="Same person as the Authorising Officer"
          description={
            hasOfficer
              ? "Their details are taken from the Authorising Officer and stay in step."
              : "Add the Authorising Officer first."
          }
          checked={form.same_as_authorising_officer}
          disabled={!hasOfficer}
          onCheckedChange={(checked) => set("same_as_authorising_officer", checked)}
        />
      ) : null}
      {same ? null : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="First name"
              name="first_name"
              autoComplete="off"
              autoFocus
              value={form.first_name}
              onChange={(event) => set("first_name", event.target.value)}
              error={errors.first_name}
            />
            <TextField
              label="Last name"
              name="last_name"
              autoComplete="off"
              value={form.last_name}
              onChange={(event) => set("last_name", event.target.value)}
              error={errors.last_name}
            />
          </div>
          <TextField
            label="Job title"
            name="designation"
            value={form.designation}
            onChange={(event) => set("designation", event.target.value)}
            error={errors.designation}
          />
          <TextField
            label="Phone"
            type="tel"
            name="phone"
            value={form.phone}
            onChange={(event) => set("phone", event.target.value)}
            error={errors.phone}
          />
          <TextField
            label="Email"
            type="email"
            name="email"
            inputMode="email"
            autoCapitalize="none"
            spellCheck={false}
            value={form.email}
            onChange={(event) => set("email", event.target.value)}
            error={errors.email}
          />
        </>
      )}
      <YesNo
        label="Is this person a British citizen or settled in the UK?"
        value={form.is_settled_or_british}
        onChange={(value) => set("is_settled_or_british", value)}
      />
      <div className="flex flex-col gap-2">
        <p className="text-headline text-label">Proof of identity</p>
        {person?.has_proof_of_id ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-callout text-label-secondary min-w-0 truncate">
              {person.proof_of_id_name ?? "A document is on file"}
            </p>
            <div className="flex gap-2">
              <Button variant="gray" size="sm" onClick={() => void view()}>
                View
              </Button>
              <Button variant="gray" size="sm" onClick={() => void takeAwayProof()}>
                Remove document
              </Button>
            </div>
          </div>
        ) : null}
        <FileDrop
          label={person?.has_proof_of_id ? "Replace the document" : "Add a document"}
          description="A passport or other identity document, as a PDF, JPG or PNG up to 10 MB. It is checked for viruses when you save."
          accept={["application/pdf", "image/jpeg", "image/png"]}
          maxBytes={10 * 1024 * 1024}
          items={items}
          onFiles={(files) => setPending(files[0] ?? null)}
          onRemove={() => setPending(null)}
        />
      </div>
    </FormSheet>
  );
}
