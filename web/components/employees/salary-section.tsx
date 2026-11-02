"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useCan } from "@/components/app/session-context";
import { FormSheet } from "@/components/company/form-sheet";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/schema";
import { attempt, type Problem } from "@/lib/auth/request";
import { shortDate } from "@/lib/employees/profile";

type Schemas = components["schemas"];
type Call = Parameters<typeof attempt>[0];
type Salary = Schemas["CompensationOut"];
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

function SalaryFacts({ record }: { record: Salary }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {[
        [
          "Amount",
          `£${Number(record.amount).toLocaleString("en-GB", { minimumFractionDigits: 2 })} ${record.frequency}`,
        ],
        ["Contracted hours a week", record.contracted_hours_per_week],
        ["Effective from", shortDate(record.effective_from)],
        ["Tax code", record.tax_code],
        ["Payment type", record.payment_type],
        ["Pay band", record.pay_band],
        ["Pay schedule", record.pay_schedule],
      ].map(([name, value]) => (
        <div key={name}>
          <dt className="text-caption text-label-secondary">{name}</dt>
          <dd className="text-body text-label">{value ?? "Not set"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SalarySection({ id, hireDate }: { id: string; hireDate: string }) {
  const can = useCan();
  const [history, setHistory] = useState<Schemas["CompensationHistory"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [sheet, setSheet] = useState(false);
  if (!can("employee.compensation.read")) return null;
  async function show() {
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/employees/{employee_id}/compensation", { params: { path: { employee_id: id } } }),
    );
    setBusy(false);
    if (result.ok) setHistory(result.data);
    else setProblem(result.problem);
  }
  return (
    <Section
      title="Salary"
      action={
        history ? (
          <Button variant="plain" size="sm" onClick={() => setHistory(null)}>
            Hide salary
          </Button>
        ) : (
          <Button variant="plain" size="sm" loading={busy} onClick={() => void show()}>
            Show salary
          </Button>
        )
      }
    >
      {problem && <Alert tone="danger" title={problem.message} />}
      {!history ? (
        <p className="text-body text-label-secondary">
          Salary is hidden until you choose to show it.
        </p>
      ) : (
        <>
          {history.current ? (
            <SalaryFacts record={history.current} />
          ) : (
            <p className="text-body text-label-secondary">No current salary recorded.</p>
          )}
          {can("employee.compensation.write") && (
            <Button variant="plain" size="sm" className="mt-3" onClick={() => setSheet(true)}>
              Add salary record
            </Button>
          )}
          {history.records.length > 0 && (
            <details className="mt-4">
              <summary className="text-callout text-tint cursor-pointer">Salary history</summary>
              <div className="flex flex-col gap-4 mt-3">
                {history.records.map((r) => (
                  <div key={r.id} className="border-separator border-t pt-3">
                    <SalaryFacts record={r} />
                  </div>
                ))}
              </div>
            </details>
          )}
        </>
      )}
      {sheet && (
        <SalarySheet
          id={id}
          hireDate={hireDate}
          onClose={() => setSheet(false)}
          onSaved={() => void show()}
        />
      )}
    </Section>
  );
}

function SalarySheet({
  id,
  hireDate,
  onClose,
  onSaved,
}: {
  id: string;
  hireDate: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    amount: "",
    frequency: "annual" as Schemas["CompensationIn"]["frequency"],
    contracted_hours_per_week: "",
    effective_from: new Date().toISOString().slice(0, 10),
    tax_code_id: "",
    payment_type_id: "",
    pay_band_id: "",
    pay_schedule_id: "",
  });
  const [lookups, setLookups] = useState<Record<string, { id: string; name: string }[]>>({});
  const [check, setCheck] = useState<Schemas["WageCheck"] | null>(null);
  const [checkProblem, setCheckProblem] = useState<Problem | null>(null);
  const [error, setError] = useState<string>();
  const { busy, problem, run } = useSubmit("Salary record added", () => {
    onSaved();
    onClose();
  });
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((c) => ({ ...c, [key]: value }));
  const body: Schemas["CompensationIn"] = {
    ...form,
    amount: form.amount,
    contracted_hours_per_week: form.contracted_hours_per_week || null,
    tax_code_id: form.tax_code_id || null,
    payment_type_id: form.payment_type_id || null,
    pay_band_id: form.pay_band_id || null,
    pay_schedule_id: form.pay_schedule_id || null,
  };
  useEffect(() => {
    let active = true;
    async function load() {
      const [tax, payment, bands, schedules] = await Promise.all([
        attempt((c) => c.GET("/tax-codes")),
        attempt((c) => c.GET("/payment-types")),
        attempt((c) => c.GET("/pay-bands")),
        attempt((c) => c.GET("/pay-schedules")),
      ]);
      if (active)
        setLookups({
          tax_code_id: tax.ok ? tax.data.map((t) => ({ id: t.id, name: t.code })) : [],
          payment_type_id: payment.ok ? payment.data : [],
          pay_band_id: bands.ok ? bands.data : [],
          pay_schedule_id: schedules.ok ? schedules.data : [],
        });
    }
    void load();
    return () => {
      active = false;
    };
  }, []);
  // A preview is read-only. Ignore stale results if the person changes a field while it loads.
  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      if (!form.amount || !form.effective_from) return;
      const result = await attempt((c) =>
        c.POST("/employees/{employee_id}/compensation/check", {
          params: { path: { employee_id: id } },
          body: {
            amount: form.amount,
            frequency: form.frequency,
            contracted_hours_per_week: form.contracted_hours_per_week || null,
            effective_from: form.effective_from,
          },
        }),
      );
      if (active) {
        setCheck(result.ok ? result.data : null);
        setCheckProblem(result.ok ? null : result.problem);
      }
    }, 300);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [id, form.amount, form.frequency, form.contracted_hours_per_week, form.effective_from]);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!form.amount || !form.effective_from)
      return setError("Enter an amount and an effective date.");
    setError(undefined);
    await run((c) =>
      c.POST("/employees/{employee_id}/compensation", {
        params: { path: { employee_id: id } },
        body,
      }),
    );
  }
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Add salary record"
      description="Previous salary records are kept in history."
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      <TextField
        label="Amount (£)"
        name="amount"
        type="number"
        autoFocus
        value={form.amount}
        onChange={(e) => set("amount", e.target.value)}
        error={error}
      />
      <Select
        label="Frequency"
        name="frequency"
        value={form.frequency}
        onChange={(e) => set("frequency", e.target.value as typeof form.frequency)}
      >
        {["annual", "monthly", "hourly"].map((f) => (
          <option key={f} value={f}>
            {f}
          </option>
        ))}
      </Select>
      <TextField
        label="Contracted hours a week"
        name="contracted_hours_per_week"
        type="number"
        value={form.contracted_hours_per_week}
        onChange={(e) => set("contracted_hours_per_week", e.target.value)}
      />
      <DatePicker
        label="Effective from"
        name="effective_from"
        min={hireDate}
        value={form.effective_from}
        onChange={(v) => set("effective_from", v ?? "")}
      />
      {check && (
        <Alert tone={check.below_minimum ? "warning" : "info"} title={check.message}>
          {check.hourly_rate != null && (
            <p>
              Estimated hourly pay: £{check.hourly_rate}
              {check.minimum_rate != null ? ` · Age-band minimum: £${check.minimum_rate}` : ""}
            </p>
          )}
          <a href={check.source} target="_blank" rel="noreferrer" className="underline">
            Check GOV.UK rates
          </a>
        </Alert>
      )}
      {checkProblem && <Alert tone="warning" title={checkProblem.message} />}
      {(
        [
          ["tax_code_id", "Tax code"],
          ["payment_type_id", "Payment type"],
          ["pay_band_id", "Pay band"],
          ["pay_schedule_id", "Pay schedule"],
        ] as const
      ).map(([key, title]) => (
        <Select
          key={key}
          label={title}
          name={key}
          value={form[key]}
          onChange={(e) => set(key, e.target.value)}
        >
          <option value="">Not set</option>
          {lookups[key]?.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </Select>
      ))}
    </FormSheet>
  );
}
