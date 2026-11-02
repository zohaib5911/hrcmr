"use client";

import { Banknote, Calendar, Landmark, Percent, Wallet, type LucideIcon } from "lucide-react";
import { useState, type ReactNode } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { Icon } from "@/components/ui/icon";
import { NumberField } from "@/components/ui/number-field";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import { Toggle } from "@/components/ui/toggle";
import type { components } from "@/lib/api/client";
import {
  bandRange,
  CURRENCIES,
  FREQUENCIES,
  formatMoney,
  percent,
  scheduleSummary,
  type Frequency,
  type PayDayKind,
} from "@/lib/company/pay";
import { WEEKDAYS } from "@/lib/company/working-pattern";

import { PaySheet } from "./pay-sheet";

type Schemas = components["schemas"];

interface ManagedListProps<T extends { id: string }> {
  title: string;
  description: string;
  addLabel: string;
  heading: string;
  mayEdit: boolean;
  items: T[];
  icon: LucideIcon;
  empty: { title: string; description: string };
  row: (item: T) => { title: string; detail: string };
  sheet: (item: T | null, close: () => void) => ReactNode;
}

/** The list every pay setting shares: a grouped list of rows, "Add" and an editing sheet. */
function ManagedList<T extends { id: string }>(props: ManagedListProps<T>) {
  const { items, mayEdit, icon } = props;
  const [editing, setEditing] = useState<T | "new" | null>(null);
  const add = <Button onClick={() => setEditing("new")}>{props.addLabel}</Button>;
  return (
    <>
      <PageHeader
        title={props.title}
        description={props.description}
        actions={mayEdit ? add : null}
      />
      {items.length === 0 ? (
        <div className="bg-elevated rounded-card shadow-e1">
          <EmptyState
            icon={icon}
            title={props.empty.title}
            description={props.empty.description}
            {...(mayEdit ? { action: add } : {})}
          />
        </div>
      ) : (
        <GroupedList heading={props.heading}>
          {items.map((item) => {
            const { title, detail } = props.row(item);
            return (
              <GroupedRow
                key={item.id}
                title={title}
                detail={detail}
                icon={<Icon icon={icon} />}
                {...(mayEdit ? { onClick: () => setEditing(item) } : {})}
              />
            );
          })}
        </GroupedList>
      )}
      {editing ? props.sheet(editing === "new" ? null : editing, () => setEditing(null)) : null}
    </>
  );
}

const required = (value: string, message: string) => (value.trim() ? null : message);
function problems(found: Record<string, string | null>): Record<string, string> | null {
  const real = Object.fromEntries(Object.entries(found).filter(([, v]) => v)) as Record<
    string,
    string
  >;
  return Object.keys(real).length > 0 ? real : null;
}

// --- bank accounts ---------------------------------------------------------------------------

type BankAccount = Schemas["BankAccountOut"];

/** `/company/bank-accounts`: the company's accounts. Numbers are kept encrypted and shown masked. */
export function BankAccountsPage({ accounts }: { accounts: BankAccount[] }) {
  const mayEdit = useCan()("company.profile.write");
  return (
    <ManagedList
      title="Bank accounts"
      description="Where the company pays from. Numbers are stored encrypted and only the last digits are ever shown."
      addLabel="Add bank account"
      heading="Your accounts"
      mayEdit={mayEdit}
      items={accounts}
      icon={Landmark}
      empty={{
        title: "No bank accounts yet",
        description: "Add the account your company pays wages from.",
      }}
      row={(a) => ({
        title: a.is_primary ? `${a.label} (main)` : a.label,
        detail: `${a.bank_name}, ${a.sort_code_masked}, ${a.account_number_masked}`,
      })}
      sheet={(account, close) => (
        <BankAccountSheet key={account?.id ?? "new"} account={account} onClose={close} />
      )}
    />
  );
}

function BankAccountSheet({
  account,
  onClose,
}: {
  account: BankAccount | null;
  onClose: () => void;
}) {
  const [label, setLabel] = useState(account?.label ?? "");
  const [bank, setBank] = useState(account?.bank_name ?? "");
  const [holder, setHolder] = useState(account?.account_holder ?? "");
  const [sortCode, setSortCode] = useState("");
  const [number, setNumber] = useState("");
  const [primary, setPrimary] = useState(account?.is_primary ?? false);
  const digits = (value: string, length: number) =>
    new RegExp(`^\\d{${length}}$`).test(value.replace(/[\s-]/g, ""));

  return (
    <PaySheet
      noun="Bank account"
      title={account ? "Edit bank account" : "Add bank account"}
      existing={account !== null}
      archiveDetail="It stops appearing in lists. Make another account the main one first."
      onClose={onClose}
      validate={() =>
        problems({
          label: required(label, "Give the account a label."),
          bank_name: required(bank, "Enter the bank's name."),
          account_holder: required(holder, "Enter the name on the account."),
          // On an existing account the numbers are optional: leaving them blank keeps them.
          sort_code:
            account && !sortCode
              ? null
              : digits(sortCode, 6)
                ? null
                : "A sort code is 6 digits, such as 12-34-56.",
          account_number:
            account && !number
              ? null
              : digits(number, 8)
                ? null
                : "A UK account number is 8 digits.",
        })
      }
      save={(client) =>
        account
          ? client.PATCH("/bank-accounts/{account_id}", {
              params: { path: { account_id: account.id } },
              body: {
                label,
                bank_name: bank,
                account_holder: holder,
                is_primary: primary,
                ...(sortCode ? { sort_code: sortCode } : {}),
                ...(number ? { account_number: number } : {}),
              },
            })
          : client.POST("/bank-accounts", {
              body: {
                label,
                bank_name: bank,
                account_holder: holder,
                sort_code: sortCode,
                account_number: number,
                is_primary: primary,
              },
            })
      }
      {...(account
        ? {
            remove: (client) =>
              client.DELETE("/bank-accounts/{account_id}", {
                params: { path: { account_id: account.id } },
              }),
          }
        : {})}
    >
      {(errors) => (
        <>
          <TextField
            label="Label"
            autoFocus
            maxLength={80}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            error={errors.label}
          />
          <TextField
            label="Bank"
            maxLength={120}
            value={bank}
            onChange={(e) => setBank(e.target.value)}
            error={errors.bank_name}
          />
          <TextField
            label="Name on the account"
            maxLength={120}
            value={holder}
            onChange={(e) => setHolder(e.target.value)}
            error={errors.account_holder}
          />
          <TextField
            label={account ? "Sort code (blank keeps it)" : "Sort code"}
            inputMode="numeric"
            autoComplete="off"
            maxLength={8}
            hint={account ? `Now ${account.sort_code_masked}` : "Six digits, such as 12-34-56."}
            value={sortCode}
            onChange={(e) => setSortCode(e.target.value)}
            error={errors.sort_code}
          />
          <TextField
            label={account ? "Account number (blank keeps it)" : "Account number"}
            inputMode="numeric"
            autoComplete="off"
            maxLength={8}
            hint={account ? `Now ${account.account_number_masked}` : "Eight digits."}
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            error={errors.account_number}
          />
          <Toggle
            label="Main account"
            description="The one used unless another is chosen."
            checked={primary}
            disabled={account?.is_primary === true}
            onCheckedChange={setPrimary}
          />
        </>
      )}
    </PaySheet>
  );
}

// --- tax codes -------------------------------------------------------------------------------

type TaxCode = Schemas["TaxCodeOut"];

export function TaxCodesPage({ codes }: { codes: TaxCode[] }) {
  const mayEdit = useCan()("settings.tax_code.write");
  return (
    <ManagedList
      title="Tax codes"
      description="The tax codes your company uses, and the share of pay each one deducts."
      addLabel="Add tax code"
      heading="Your tax codes"
      mayEdit={mayEdit}
      items={codes}
      icon={Percent}
      empty={{
        title: "No tax codes yet",
        description: "Add the codes you use, such as 1257L, with the percentage each deducts.",
      }}
      row={(c) => ({
        title: c.code,
        detail: [percent(c.deduction_percentage), c.reference].filter(Boolean).join(", "),
      })}
      sheet={(code, close) => <TaxCodeSheet key={code?.id ?? "new"} code={code} onClose={close} />}
    />
  );
}

function TaxCodeSheet({ code, onClose }: { code: TaxCode | null; onClose: () => void }) {
  const [value, setValue] = useState(code?.code ?? "");
  const [reference, setReference] = useState(code?.reference ?? "");
  const [rate, setRate] = useState<number | null>(code ? Number(code.deduction_percentage) : null);
  const body = () => ({
    code: value,
    reference: reference.trim() || null,
    deduction_percentage: (rate ?? 0).toFixed(2),
  });
  return (
    <PaySheet
      noun="Tax code"
      title={code ? "Edit tax code" : "Add tax code"}
      existing={code !== null}
      archiveDetail="It stops appearing in lists."
      onClose={onClose}
      validate={() =>
        problems({
          code: required(value, "Enter the tax code, such as 1257L."),
          deduction_percentage:
            rate === null || rate < 0 || rate > 100 ? "Enter a percentage from 0 to 100." : null,
        })
      }
      save={(client) =>
        code
          ? client.PUT("/tax-codes/{tax_code_id}", {
              params: { path: { tax_code_id: code.id } },
              body: body(),
            })
          : client.POST("/tax-codes", { body: body() })
      }
      {...(code
        ? {
            remove: (client) =>
              client.DELETE("/tax-codes/{tax_code_id}", {
                params: { path: { tax_code_id: code.id } },
              }),
          }
        : {})}
    >
      {(errors) => (
        <>
          <TextField
            label="Code"
            autoFocus
            maxLength={12}
            value={value}
            onChange={(e) => setValue(e.target.value.toUpperCase())}
            error={errors.code}
          />
          <TextField
            label="Reference (optional)"
            maxLength={80}
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            error={errors.reference}
          />
          <NumberField
            label="Deduction"
            decimals={2}
            step={0.5}
            min={0}
            max={100}
            hint="The percentage of pay taken."
            value={rate}
            onChange={setRate}
            error={errors.deduction_percentage}
          />
        </>
      )}
    </PaySheet>
  );
}

// --- payment types ---------------------------------------------------------------------------

type PaymentType = Schemas["PaymentTypeOut"];

export function PaymentTypesPage({ types }: { types: PaymentType[] }) {
  const mayEdit = useCan()("settings.payment_type.write");
  return (
    <ManagedList
      title="Payment types"
      description="The ways people can be paid, each with the lowest hourly rate you allow."
      addLabel="Add payment type"
      heading="Your payment types"
      mayEdit={mayEdit}
      items={types}
      icon={Wallet}
      empty={{
        title: "No payment types yet",
        description: "Add types such as Hourly or Salaried, with a minimum hourly rate.",
      }}
      row={(t) => ({
        title: t.name,
        detail: `From ${formatMoney(t.min_hourly_rate, "GBP", 2)} an hour`,
      })}
      sheet={(type, close) => (
        <PaymentTypeSheet key={type?.id ?? "new"} type={type} onClose={close} />
      )}
    />
  );
}

function PaymentTypeSheet({ type, onClose }: { type: PaymentType | null; onClose: () => void }) {
  const [name, setName] = useState(type?.name ?? "");
  const [rate, setRate] = useState<number | null>(type ? Number(type.min_hourly_rate) : null);
  const body = () => ({ name, min_hourly_rate: (rate ?? 0).toFixed(2) });
  return (
    <PaySheet
      noun="Payment type"
      title={type ? "Edit payment type" : "Add payment type"}
      existing={type !== null}
      archiveDetail="It stops appearing in lists."
      onClose={onClose}
      validate={() =>
        problems({
          name: required(name, "Give the payment type a name."),
          min_hourly_rate: rate === null || rate < 0 ? "Enter a rate of 0 or more." : null,
        })
      }
      save={(client) =>
        type
          ? client.PUT("/payment-types/{type_id}", {
              params: { path: { type_id: type.id } },
              body: body(),
            })
          : client.POST("/payment-types", { body: body() })
      }
      {...(type
        ? {
            remove: (client) =>
              client.DELETE("/payment-types/{type_id}", {
                params: { path: { type_id: type.id } },
              }),
          }
        : {})}
    >
      {(errors) => (
        <>
          <TextField
            label="Name"
            autoFocus
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={errors.name}
          />
          <NumberField
            label="Minimum hourly rate"
            unit="currency"
            min={0}
            step={0.25}
            value={rate}
            onChange={setRate}
            error={errors.min_hourly_rate}
          />
        </>
      )}
    </PaySheet>
  );
}

// --- pay bands -------------------------------------------------------------------------------

type PayBand = Schemas["PayBandOut"];

export function PayBandsPage({ bands }: { bands: PayBand[] }) {
  const mayEdit = useCan()("settings.pay_band.write");
  return (
    <ManagedList
      title="Pay bands"
      description="Pay ranges for grades or roles, lowest first."
      addLabel="Add pay band"
      heading="Your pay bands"
      mayEdit={mayEdit}
      items={bands}
      icon={Banknote}
      empty={{
        title: "No pay bands yet",
        description: "Add a band for each grade, with the lowest and highest yearly pay.",
      }}
      row={(b) => ({
        title: b.name,
        detail: bandRange(b.min_annual, b.max_annual, b.currency),
      })}
      sheet={(band, close) => <PayBandSheet key={band?.id ?? "new"} band={band} onClose={close} />}
    />
  );
}

function PayBandSheet({ band, onClose }: { band: PayBand | null; onClose: () => void }) {
  const [name, setName] = useState(band?.name ?? "");
  const [min, setMin] = useState<number | null>(band ? Number(band.min_annual) : null);
  const [max, setMax] = useState<number | null>(band ? Number(band.max_annual) : null);
  const [currency, setCurrency] = useState(band?.currency ?? "GBP");
  const money = currency === "GBP" ? ("currency" as const) : ("plain" as const);
  const body = () => ({
    name,
    min_annual: (min ?? 0).toFixed(2),
    max_annual: (max ?? 0).toFixed(2),
    currency,
  });
  return (
    <PaySheet
      noun="Pay band"
      title={band ? "Edit pay band" : "Add pay band"}
      existing={band !== null}
      archiveDetail="It stops appearing in lists."
      onClose={onClose}
      validate={() =>
        problems({
          name: required(name, "Give the pay band a name."),
          min_annual: min === null ? "Enter the lowest yearly pay." : null,
          max_annual:
            max === null
              ? "Enter the highest yearly pay."
              : min !== null && max < min
                ? "The highest cannot be less than the lowest."
                : null,
        })
      }
      save={(client) =>
        band
          ? client.PUT("/pay-bands/{band_id}", {
              params: { path: { band_id: band.id } },
              body: body(),
            })
          : client.POST("/pay-bands", { body: body() })
      }
      {...(band
        ? {
            remove: (client) =>
              client.DELETE("/pay-bands/{band_id}", { params: { path: { band_id: band.id } } }),
          }
        : {})}
    >
      {(errors) => (
        <>
          <TextField
            label="Name"
            autoFocus
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={errors.name}
          />
          <Select label="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <NumberField
            label="Lowest yearly pay"
            unit={money}
            decimals={0}
            min={0}
            step={500}
            value={min}
            onChange={setMin}
            error={errors.min_annual}
          />
          <NumberField
            label="Highest yearly pay"
            unit={money}
            decimals={0}
            min={0}
            step={500}
            value={max}
            onChange={setMax}
            error={errors.max_annual}
          />
        </>
      )}
    </PaySheet>
  );
}

// --- pay schedules ---------------------------------------------------------------------------

type PaySchedule = Schemas["PayScheduleOut"];

export function PaySchedulesPage({ schedules }: { schedules: PaySchedule[] }) {
  const mayEdit = useCan()("settings.pay_schedule.write");
  return (
    <ManagedList
      title="Pay schedules"
      description="How often people are paid, and on which day."
      addLabel="Add pay schedule"
      heading="Your pay schedules"
      mayEdit={mayEdit}
      items={schedules}
      icon={Calendar}
      empty={{
        title: "No pay schedules yet",
        description: "Add one for each way you pay, such as monthly on the 25th.",
      }}
      row={(s) => ({
        title: s.name,
        detail: scheduleSummary(s.frequency, s.pay_day_kind, s.pay_day_value),
      })}
      sheet={(schedule, close) => (
        <PayScheduleSheet key={schedule?.id ?? "new"} schedule={schedule} onClose={close} />
      )}
    />
  );
}

/** The pay-day choices that make sense for a frequency: a weekday, or a day of the month. */
function PayScheduleSheet({
  schedule,
  onClose,
}: {
  schedule: PaySchedule | null;
  onClose: () => void;
}) {
  const [name, setName] = useState(schedule?.name ?? "");
  const [frequency, setFrequency] = useState<Frequency>(schedule?.frequency ?? "monthly");
  const [kind, setKind] = useState<PayDayKind>(schedule?.pay_day_kind ?? "last_working_day");
  const [value, setValue] = useState<number | null>(schedule?.pay_day_value ?? null);
  const monthly = frequency === "monthly";

  function chooseFrequency(next: Frequency) {
    setFrequency(next);
    if (next === "monthly" && kind === "weekday") {
      setKind("last_working_day");
      setValue(null);
    } else if (next !== "monthly" && kind !== "weekday") {
      setKind("weekday");
      setValue(5);
    }
  }

  const body = () => ({
    name,
    frequency,
    pay_day_kind: kind,
    pay_day_value: kind === "weekday" || kind === "day_of_month" ? value : null,
  });

  return (
    <PaySheet
      noun="Pay schedule"
      title={schedule ? "Edit pay schedule" : "Add pay schedule"}
      existing={schedule !== null}
      archiveDetail="It stops appearing in lists."
      onClose={onClose}
      validate={() =>
        problems({
          name: required(name, "Give the pay schedule a name."),
          pay_day_value:
            (kind === "weekday" || kind === "day_of_month") && value === null
              ? "Choose the pay day."
              : null,
        })
      }
      save={(client) =>
        schedule
          ? client.PUT("/pay-schedules/{schedule_id}", {
              params: { path: { schedule_id: schedule.id } },
              body: body(),
            })
          : client.POST("/pay-schedules", { body: body() })
      }
      {...(schedule
        ? {
            remove: (client) =>
              client.DELETE("/pay-schedules/{schedule_id}", {
                params: { path: { schedule_id: schedule.id } },
              }),
          }
        : {})}
    >
      {(errors) => (
        <>
          <TextField
            label="Name"
            autoFocus
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={errors.name}
          />
          <Select
            label="How often"
            value={frequency}
            onChange={(e) => chooseFrequency(e.target.value as Frequency)}
          >
            {FREQUENCIES.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </Select>
          {monthly ? (
            <Select
              label="Pay day"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value as PayDayKind);
                setValue(e.target.value === "day_of_month" ? (value ?? 25) : null);
              }}
            >
              <option value="last_working_day">The last working day</option>
              <option value="last_day">The last day of the month</option>
              <option value="day_of_month">A day of the month</option>
            </Select>
          ) : (
            <Select
              label="Pay day"
              value={String(value ?? 5)}
              onChange={(e) => setValue(Number(e.target.value))}
              error={errors.pay_day_value}
            >
              {WEEKDAYS.map((day, index) => (
                <option key={day} value={index + 1}>
                  {day}
                </option>
              ))}
            </Select>
          )}
          {monthly && kind === "day_of_month" ? (
            <NumberField
              label="Day of the month"
              min={1}
              max={28}
              hint="1 to 28, so it exists in every month."
              value={value}
              onChange={setValue}
              error={errors.pay_day_value}
            />
          ) : null}
        </>
      )}
    </PaySheet>
  );
}
