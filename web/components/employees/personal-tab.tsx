"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { useCan } from "@/components/app/session-context";
import { FormSheet } from "@/components/company/form-sheet";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/schema";
import { attempt, type Problem } from "@/lib/auth/request";
import { shortDate } from "@/lib/employees/profile";
import {
  addressLine,
  GENDERS,
  labelOf,
  MARITAL_STATUSES,
  RELATIONSHIPS,
  type Contact,
  type PersonalTab as Personal,
  type Relationship,
} from "@/lib/employees/personal";

type Revealed = components["schemas"]["Revealed"];
type Field = "identity" | "bank";
type Call = Parameters<typeof attempt>[0];
type Errors = Record<string, string | undefined>;

const REVEAL_SECONDS = 60;
const today = () => new Date().toISOString().slice(0, 10);

/** Runs a call; on success toasts, refreshes the page data and closes. A problem stays in the sheet. */
function useSubmit(success: string, onClose: () => void) {
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  async function run(call: Call): Promise<Problem | null> {
    setBusy(true);
    setProblem(null);
    const outcome = await attempt(call);
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: success, tone: "success" });
      router.refresh();
      onClose();
      return null;
    }
    setProblem(outcome.problem);
    return outcome.problem;
  }
  return { busy, problem, setProblem, run };
}

const blank = (value: string) => value.trim() || null;

function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="bg-elevated rounded-card shadow-e1 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-headline text-label">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-caption text-label-secondary">{label}</dt>
          <dd className="text-body text-label break-words">
            {value || <span className="text-label-secondary">Not set</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** The Personal tab (plan 8.3). Every section saves with its own button; nothing saves on its own. */
export function PersonalTab({ id, personal }: { id: string; personal: Personal }) {
  const can = useCan();
  const mayEdit = can("employee.profile.write", "employee.profile.write_own");
  const mayEditSensitive = can("employee.sensitive_data.write");
  const toast = useToast();
  const [sheet, setSheet] = useState<
    | { kind: "details" | "address" | "bank" }
    | { kind: "contact"; contact: Contact | null }
    | { kind: "identity"; current: Revealed }
    | null
  >(null);
  const [pending, setPending] = useState<{ field: Field; then: (r: Revealed) => void } | null>(
    null,
  );
  const [shown, setShown] = useState<Revealed | null>(null);

  useEffect(() => {
    if (!shown) return;
    const timer = setTimeout(() => setShown(null), REVEAL_SECONDS * 1000);
    return () => clearTimeout(timer);
  }, [shown]);

  /** Fetch the full values. If the person has not just confirmed who they are, ask for the password first. */
  async function reveal(field: Field, then: (r: Revealed) => void) {
    const outcome = await attempt((client) =>
      client.POST("/employees/{employee_id}/reveal", {
        params: { path: { employee_id: id } },
        body: { field },
      }),
    );
    if (outcome.ok) return then(outcome.data);
    if (outcome.problem.code === "STEP_UP_REQUIRED") return setPending({ field, then });
    toast.show({ title: outcome.problem.message, tone: "danger" });
  }

  const { details, address, contacts, identity, bank } = personal;
  const close = () => setSheet(null);

  return (
    <div className="flex flex-col gap-6">
      <Section
        title="Personal details"
        action={
          mayEdit ? (
            <Button variant="gray" size="sm" onClick={() => setSheet({ kind: "details" })}>
              Edit details
            </Button>
          ) : null
        }
      >
        <Facts
          rows={[
            ["First name", details.first_name],
            ["Last name", details.last_name],
            ["Email", details.email],
            ["Contact number", details.phone],
            ["Alternative number", details.alt_phone],
            ["Date of birth", details.date_of_birth ? shortDate(details.date_of_birth) : null],
            ["Gender", labelOf(GENDERS, details.gender)],
            ["Marital status", labelOf(MARITAL_STATUSES, details.marital_status)],
            ["Nationality", details.nationality],
          ]}
        />
      </Section>

      <Section
        title="Correspondence address"
        action={
          mayEdit ? (
            <Button variant="gray" size="sm" onClick={() => setSheet({ kind: "address" })}>
              {address ? "Edit address" : "Add address"}
            </Button>
          ) : null
        }
      >
        {address ? (
          <p className="text-body text-label">{addressLine(address)}</p>
        ) : (
          <p className="text-callout text-label-secondary">No address recorded yet.</p>
        )}
      </Section>

      <Section
        title="Emergency contacts"
        action={
          mayEdit ? (
            <Button
              variant="gray"
              size="sm"
              onClick={() => setSheet({ kind: "contact", contact: null })}
            >
              Add contact
            </Button>
          ) : null
        }
      >
        {contacts.length === 0 ? (
          <p className="text-callout text-label-secondary">No emergency contacts yet.</p>
        ) : (
          <ul className="divide-separator divide-y">
            {contacts.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 py-3 first:pt-0">
                <div className="min-w-0">
                  <p className="text-body text-label truncate">{c.name}</p>
                  <p className="text-callout text-label-secondary truncate">
                    {labelOf(RELATIONSHIPS, c.relationship)} · {c.phone}
                  </p>
                </div>
                {mayEdit ? (
                  <Button
                    variant="gray"
                    size="sm"
                    aria-label={`Edit ${c.name}`}
                    onClick={() => setSheet({ kind: "contact", contact: c })}
                  >
                    Edit
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Section>

      {personal.sensitive_visible && identity ? (
        <Section
          title="National Insurance and passport"
          action={
            <div className="flex gap-2">
              {shown?.identity ? (
                <Button variant="gray" size="sm" onClick={() => setShown(null)}>
                  Hide
                </Button>
              ) : (
                <Button
                  variant="gray"
                  size="sm"
                  onClick={() => void reveal("identity", (r) => setShown(r))}
                >
                  Show
                </Button>
              )}
              {mayEditSensitive ? (
                <Button
                  variant="gray"
                  size="sm"
                  onClick={() =>
                    void reveal("identity", (current) => setSheet({ kind: "identity", current }))
                  }
                >
                  Edit
                </Button>
              ) : null}
            </div>
          }
        >
          <Facts
            rows={[
              ["National Insurance number", shown?.identity?.ni_number ?? identity.ni_number],
              ["Passport number", shown?.identity?.passport_number ?? identity.passport_number],
              ["Passport country", identity.passport_country],
              [
                "Passport expiry",
                identity.passport_expiry ? shortDate(identity.passport_expiry) : null,
              ],
            ]}
          />
        </Section>
      ) : null}

      {personal.sensitive_visible ? (
        <Section
          title="Bank details"
          action={
            <div className="flex gap-2">
              {bank ? (
                shown?.bank ? (
                  <Button variant="gray" size="sm" onClick={() => setShown(null)}>
                    Hide
                  </Button>
                ) : (
                  <Button
                    variant="gray"
                    size="sm"
                    onClick={() => void reveal("bank", (r) => setShown(r))}
                  >
                    Show
                  </Button>
                )
              ) : null}
              {mayEditSensitive ? (
                <Button variant="gray" size="sm" onClick={() => setSheet({ kind: "bank" })}>
                  {bank ? "Replace account" : "Add account"}
                </Button>
              ) : null}
            </div>
          }
        >
          {bank ? (
            <Facts
              rows={[
                ["Account holder", bank.account_holder],
                ["Bank", bank.bank_name],
                ["Sort code", shown?.bank?.sort_code ?? bank.sort_code],
                ["Account number", shown?.bank?.account_number ?? bank.account_number],
              ]}
            />
          ) : (
            <p className="text-callout text-label-secondary">No bank details recorded yet.</p>
          )}
        </Section>
      ) : null}

      {shown ? (
        <p className="text-footnote text-label-secondary" role="status">
          Shown for {REVEAL_SECONDS} seconds. This was recorded in the audit trail.
        </p>
      ) : null}

      {sheet?.kind === "details" ? (
        <DetailsSheet id={id} details={details} onClose={close} />
      ) : null}
      {sheet?.kind === "address" ? (
        <AddressSheet id={id} address={address} onClose={close} />
      ) : null}
      {sheet?.kind === "contact" ? (
        <ContactSheet id={id} contact={sheet.contact} onClose={close} />
      ) : null}
      {sheet?.kind === "identity" ? (
        <IdentitySheet
          id={id}
          current={sheet.current}
          country={identity?.passport_country ?? null}
          expiry={identity?.passport_expiry ?? null}
          onClose={close}
        />
      ) : null}
      {sheet?.kind === "bank" ? <BankSheet id={id} bank={bank} onClose={close} /> : null}
      {pending ? (
        <ConfirmItsYou
          id={id}
          field={pending.field}
          onDone={(r) => {
            const { then } = pending;
            setPending(null);
            then(r);
          }}
          onClose={() => setPending(null)}
        />
      ) : null}
    </div>
  );
}

function ConfirmItsYou({
  id,
  field,
  onDone,
  onClose,
}: {
  id: string;
  field: Field;
  onDone: (r: Revealed) => void;
  onClose: () => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | undefined>();
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!password) return setError("Enter your password.");
    setError(undefined);
    setProblem(null);
    setBusy(true);
    const confirmed = await attempt((client) =>
      client.POST("/auth/step-up", { body: { password } }),
    );
    if (!confirmed.ok) {
      setBusy(false);
      return setError(confirmed.problem.message);
    }
    const outcome = await attempt((client) =>
      client.POST("/employees/{employee_id}/reveal", {
        params: { path: { employee_id: id } },
        body: { field },
      }),
    );
    setBusy(false);
    if (outcome.ok) onDone(outcome.data);
    else setProblem(outcome.problem);
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Confirm it is you"
      description="For your security, confirm your password to see these details. Each time they are shown it is recorded."
      onSubmit={submit}
      busy={busy}
      problem={problem}
      saveLabel="Confirm"
    >
      <TextField
        label="Your password"
        name="password"
        type="password"
        autoComplete="current-password"
        autoFocus
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={error}
      />
    </FormSheet>
  );
}

function DetailsSheet({
  id,
  details,
  onClose,
}: {
  id: string;
  details: Personal["details"];
  onClose: () => void;
}) {
  const [form, setForm] = useState({
    ...details,
    phone: details.phone ?? "",
    alt_phone: details.alt_phone ?? "",
    nationality: details.nationality ?? "",
  });
  const [errors, setErrors] = useState<Errors>({});
  const { busy, problem, setProblem, run } = useSubmit("Details saved", onClose);
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  async function save(event: FormEvent) {
    event.preventDefault();
    const found: Errors = {};
    if (!form.first_name.trim()) found.first_name = "Enter a first name.";
    if (!form.last_name.trim()) found.last_name = "Enter a last name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()))
      found.email = "Enter an email address.";
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0) return;
    const failed = await run((client) =>
      client.PUT("/employees/{employee_id}/personal", {
        params: { path: { employee_id: id } },
        body: {
          ...form,
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          email: form.email.trim(),
          phone: blank(form.phone),
          alt_phone: blank(form.alt_phone),
          nationality: blank(form.nationality),
        },
      }),
    );
    if (failed?.field && failed.field in form) setErrors({ [failed.field]: failed.message });
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Edit personal details"
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      <TextField
        label="First name"
        name="first_name"
        autoFocus
        value={form.first_name}
        onChange={(e) => set("first_name", e.target.value)}
        error={errors.first_name}
      />
      <TextField
        label="Last name"
        name="last_name"
        value={form.last_name}
        onChange={(e) => set("last_name", e.target.value)}
        error={errors.last_name}
      />
      <TextField
        label="Email"
        name="email"
        type="email"
        value={form.email}
        onChange={(e) => set("email", e.target.value)}
        error={errors.email}
      />
      <TextField
        label="Contact number"
        name="phone"
        type="tel"
        value={form.phone}
        onChange={(e) => set("phone", e.target.value)}
        error={errors.phone}
      />
      <TextField
        label="Alternative number"
        name="alt_phone"
        type="tel"
        value={form.alt_phone}
        onChange={(e) => set("alt_phone", e.target.value)}
        error={errors.alt_phone}
      />
      <DatePicker
        label="Date of birth"
        name="date_of_birth"
        value={form.date_of_birth}
        onChange={(value) => set("date_of_birth", value)}
        max={today()}
        error={errors.date_of_birth}
      />
      <Select
        label="Gender"
        name="gender"
        value={form.gender}
        onChange={(e) => set("gender", e.target.value as typeof form.gender)}
      >
        {GENDERS.map((g) => (
          <option key={g.value} value={g.value}>
            {g.label}
          </option>
        ))}
      </Select>
      <Select
        label="Marital status"
        name="marital_status"
        value={form.marital_status}
        onChange={(e) => set("marital_status", e.target.value as typeof form.marital_status)}
      >
        {MARITAL_STATUSES.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </Select>
      <TextField
        label="Nationality"
        name="nationality"
        value={form.nationality}
        onChange={(e) => set("nationality", e.target.value)}
        error={errors.nationality}
      />
    </FormSheet>
  );
}

function AddressSheet({
  id,
  address,
  onClose,
}: {
  id: string;
  address: Personal["address"];
  onClose: () => void;
}) {
  const [form, setForm] = useState({
    postcode: address?.postcode ?? "",
    line1: address?.line1 ?? "",
    line2: address?.line2 ?? "",
    line3: address?.line3 ?? "",
    city_county: address?.city_county ?? "",
    country: address?.country ?? "",
  });
  const [errors, setErrors] = useState<Errors>({});
  const [lookup, setLookup] = useState<{ busy: boolean; message?: string; failed?: boolean }>({
    busy: false,
  });
  const { busy, problem, setProblem, run } = useSubmit("Address saved", onClose);
  const set = (key: keyof typeof form, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  async function look() {
    setLookup({ busy: true });
    const outcome = await attempt((client) =>
      client.GET("/employee-lookups/postcode/{postcode}", {
        params: { path: { postcode: form.postcode } },
      }),
    );
    if (!outcome.ok) {
      setLookup({ busy: false, failed: true, message: outcome.problem.message });
      return;
    }
    const found = outcome.data;
    setForm((current) => ({
      ...current,
      postcode: found.postcode,
      city_county: [found.city, found.county].filter(Boolean).join(", ") || current.city_county,
      country: found.country ?? current.country,
    }));
    setLookup({ busy: false, message: "Town, county and country filled in. Add the street." });
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    const found: Errors = {};
    if (!form.line1.trim()) found.line1 = "Enter the first line of the address.";
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0) return;
    const failed = await run((client) =>
      client.PUT("/employees/{employee_id}/address", {
        params: { path: { employee_id: id } },
        body: {
          postcode: blank(form.postcode),
          line1: form.line1.trim(),
          line2: blank(form.line2),
          line3: blank(form.line3),
          city_county: blank(form.city_county),
          country: blank(form.country),
        },
      }),
    );
    if (failed?.field && failed.field in form) setErrors({ [failed.field]: failed.message });
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={address ? "Edit address" : "Add address"}
      description="Where we write to this person."
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      <TextField
        label="Postcode"
        name="postcode"
        autoComplete="postal-code"
        autoCapitalize="characters"
        spellCheck={false}
        autoFocus
        value={form.postcode}
        onChange={(e) => set("postcode", e.target.value)}
        error={errors.postcode}
        endAdornment={
          <Button
            variant="gray"
            size="sm"
            loading={lookup.busy}
            aria-disabled={!form.postcode.trim() || undefined}
            onClick={() => form.postcode.trim() && void look()}
          >
            Look up
          </Button>
        }
      />
      {lookup.message ? (
        <Alert tone={lookup.failed ? "warning" : "success"} title={lookup.message} />
      ) : null}
      <TextField
        label="Address line 1"
        name="line1"
        autoComplete="address-line1"
        value={form.line1}
        onChange={(e) => set("line1", e.target.value)}
        error={errors.line1}
      />
      <TextField
        label="Address line 2"
        name="line2"
        autoComplete="address-line2"
        value={form.line2}
        onChange={(e) => set("line2", e.target.value)}
      />
      <TextField
        label="Address line 3"
        name="line3"
        autoComplete="address-line3"
        value={form.line3}
        onChange={(e) => set("line3", e.target.value)}
      />
      <TextField
        label="Town and county"
        name="city_county"
        autoComplete="address-level2"
        value={form.city_county}
        onChange={(e) => set("city_county", e.target.value)}
      />
      <TextField
        label="Country"
        name="country"
        autoComplete="country-name"
        value={form.country}
        onChange={(e) => set("country", e.target.value)}
      />
    </FormSheet>
  );
}

function ContactSheet({
  id,
  contact,
  onClose,
}: {
  id: string;
  contact: Contact | null;
  onClose: () => void;
}) {
  const [form, setForm] = useState({
    name: contact?.name ?? "",
    relationship: (contact?.relationship ?? "spouse") as Relationship,
    phone: contact?.phone ?? "",
    email: contact?.email ?? "",
    address: contact?.address ?? "",
    details: contact?.details ?? "",
  });
  const [errors, setErrors] = useState<Errors>({});
  const { busy, problem, setProblem, run } = useSubmit(
    contact ? "Contact saved" : "Contact added",
    onClose,
  );
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  async function save(event: FormEvent) {
    event.preventDefault();
    const found: Errors = {};
    if (!form.name.trim()) found.name = "Enter their name.";
    if (!form.phone.trim()) found.phone = "Enter a phone number.";
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0) return;
    const body = {
      name: form.name.trim(),
      relationship: form.relationship,
      phone: form.phone.trim(),
      email: blank(form.email),
      address: blank(form.address),
      details: blank(form.details),
    };
    const failed = await run((client) =>
      contact
        ? client.PUT("/employees/{employee_id}/contacts/{contact_id}", {
            params: { path: { employee_id: id, contact_id: contact.id } },
            body,
          })
        : client.POST("/employees/{employee_id}/contacts", {
            params: { path: { employee_id: id } },
            body,
          }),
    );
    if (failed?.field && failed.field in form) setErrors({ [failed.field]: failed.message });
  }

  async function remove() {
    if (!contact) return;
    await run((client) =>
      client.DELETE("/employees/{employee_id}/contacts/{contact_id}", {
        params: { path: { employee_id: id, contact_id: contact.id } },
      }),
    );
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={contact ? "Edit emergency contact" : "Add emergency contact"}
      onSubmit={save}
      busy={busy}
      problem={problem}
      {...(contact
        ? {
            archive: {
              label: "Remove",
              question: `Remove ${contact.name}?`,
              detail: "They stop appearing as an emergency contact.",
              onConfirm: remove,
            },
          }
        : {})}
    >
      <TextField
        label="Name"
        name="name"
        autoFocus
        value={form.name}
        onChange={(e) => set("name", e.target.value)}
        error={errors.name}
      />
      <Select
        label="Relationship"
        name="relationship"
        value={form.relationship}
        onChange={(e) => set("relationship", e.target.value as Relationship)}
      >
        {RELATIONSHIPS.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </Select>
      <TextField
        label="Phone"
        name="phone"
        type="tel"
        value={form.phone}
        onChange={(e) => set("phone", e.target.value)}
        error={errors.phone}
      />
      <TextField
        label="Email (optional)"
        name="email"
        type="email"
        value={form.email}
        onChange={(e) => set("email", e.target.value)}
        error={errors.email}
      />
      <TextArea
        label="Address (optional)"
        name="address"
        value={form.address}
        onChange={(e) => set("address", e.target.value)}
      />
      <TextArea
        label="Other details (optional)"
        name="details"
        value={form.details}
        onChange={(e) => set("details", e.target.value)}
      />
    </FormSheet>
  );
}

function IdentitySheet({
  id,
  current,
  country,
  expiry,
  onClose,
}: {
  id: string;
  current: Revealed;
  country: string | null;
  expiry: string | null;
  onClose: () => void;
}) {
  const [form, setForm] = useState({
    ni_number: current.identity?.ni_number ?? "",
    passport_number: current.identity?.passport_number ?? "",
    passport_country: country ?? "",
    passport_expiry: expiry,
  });
  const [errors, setErrors] = useState<Errors>({});
  const { busy, problem, setProblem, run } = useSubmit("Identity details saved", onClose);
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((c) => ({ ...c, [key]: value }));

  async function save(event: FormEvent) {
    event.preventDefault();
    setErrors({});
    setProblem(null);
    const failed = await run((client) =>
      client.PUT("/employees/{employee_id}/identity", {
        params: { path: { employee_id: id } },
        body: {
          ni_number: blank(form.ni_number),
          passport_number: blank(form.passport_number),
          passport_country: blank(form.passport_country),
          passport_expiry: form.passport_expiry,
        },
      }),
    );
    if (failed?.field && failed.field in form) setErrors({ [failed.field]: failed.message });
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Edit National Insurance and passport"
      description="Empty a field to remove it."
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      <TextField
        label="National Insurance number"
        name="ni_number"
        autoFocus
        autoCapitalize="characters"
        spellCheck={false}
        value={form.ni_number}
        onChange={(e) => set("ni_number", e.target.value)}
        error={errors.ni_number}
        hint="For example AB 12 34 56 C."
      />
      <TextField
        label="Passport number"
        name="passport_number"
        autoCapitalize="characters"
        spellCheck={false}
        value={form.passport_number}
        onChange={(e) => set("passport_number", e.target.value)}
        error={errors.passport_number}
      />
      <TextField
        label="Passport country"
        name="passport_country"
        value={form.passport_country}
        onChange={(e) => set("passport_country", e.target.value)}
      />
      <DatePicker
        label="Passport expiry"
        name="passport_expiry"
        value={form.passport_expiry}
        onChange={(value) => set("passport_expiry", value)}
      />
    </FormSheet>
  );
}

function BankSheet({
  id,
  bank,
  onClose,
}: {
  id: string;
  bank: Personal["bank"];
  onClose: () => void;
}) {
  const [form, setForm] = useState({
    account_holder: bank?.account_holder ?? "",
    bank_name: bank?.bank_name ?? "",
    sort_code: "",
    account_number: "",
  });
  const [errors, setErrors] = useState<Errors>({});
  const { busy, problem, setProblem, run } = useSubmit("Bank details saved", onClose);
  const set = (key: keyof typeof form, value: string) => setForm((c) => ({ ...c, [key]: value }));

  async function save(event: FormEvent) {
    event.preventDefault();
    const found: Errors = {};
    if (!form.account_holder.trim()) found.account_holder = "Enter the name on the account.";
    if (!form.bank_name.trim()) found.bank_name = "Enter the bank's name.";
    if (!/^\d{2}[\s-]?\d{2}[\s-]?\d{2}$/.test(form.sort_code.trim()))
      found.sort_code = "A sort code is 6 digits, such as 12-34-56.";
    if (!/^\d{8}$/.test(form.account_number.replace(/\s/g, "")))
      found.account_number = "An account number is 8 digits.";
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0) return;
    const failed = await run((client) =>
      client.PUT("/employees/{employee_id}/bank", {
        params: { path: { employee_id: id } },
        body: form,
      }),
    );
    if (failed?.field && failed.field in form) setErrors({ [failed.field]: failed.message });
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={bank ? "Replace bank account" : "Add bank account"}
      description={
        bank
          ? "The account now on file is kept as history. Enter the new account in full."
          : "Where this person is paid."
      }
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      <TextField
        label="Account holder"
        name="account_holder"
        autoFocus
        value={form.account_holder}
        onChange={(e) => set("account_holder", e.target.value)}
        error={errors.account_holder}
      />
      <TextField
        label="Bank"
        name="bank_name"
        value={form.bank_name}
        onChange={(e) => set("bank_name", e.target.value)}
        error={errors.bank_name}
      />
      <TextField
        label="Sort code"
        name="sort_code"
        inputMode="numeric"
        autoComplete="off"
        value={form.sort_code}
        onChange={(e) => set("sort_code", e.target.value)}
        error={errors.sort_code}
      />
      <TextField
        label="Account number"
        name="account_number"
        inputMode="numeric"
        autoComplete="off"
        value={form.account_number}
        onChange={(e) => set("account_number", e.target.value)}
        error={errors.account_number}
      />
    </FormSheet>
  );
}
