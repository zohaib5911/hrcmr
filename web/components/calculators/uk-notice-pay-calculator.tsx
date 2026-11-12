"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import {
  calculateNotice,
  type Arrangement,
  type Giver,
  type Jurisdiction,
  type NoticeResult,
  type PayMode,
  type Status,
} from "@/lib/calculators/uk-notice-pay-calculator";

const gbp = (n: number) => `£${n.toLocaleString("en-GB", { minimumFractionDigits: 2 })}`;

export function UkNoticePayCalculator() {
  const [jurisdiction, setJurisdiction] = useState<Jurisdiction>("gb");
  const [giver, setGiver] = useState<Giver>("employer");
  const [status, setStatus] = useState<Status>("employee");
  const [startDate, setStartDate] = useState("");
  const [noticeDate, setNoticeDate] = useState("");
  const [contractWeeks, setContractWeeks] = useState("");
  const [payMode, setPayMode] = useState<PayMode>("weekly");
  const [amount, setAmount] = useState("");
  const [arrangement, setArrangement] = useState<Arrangement>("work");
  const [result, setResult] = useState<ReturnType<typeof calculateNotice> | null>(null);

  const reset = () => setResult(null);

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          setResult(
            calculateNotice({
              jurisdiction,
              giver,
              status,
              startDate,
              noticeDate,
              contractWeeks: contractWeeks.trim() === "" ? null : Number(contractWeeks),
              payMode,
              amount: Number(amount),
              arrangement,
            }),
          );
        }}
      >
        <h2 className="text-title-2 text-label">Your situation</h2>
        <Select
          label="Where do you work?"
          value={jurisdiction}
          onChange={(e) => {
            setJurisdiction(e.target.value as Jurisdiction);
            reset();
          }}
        >
          <option value="gb">England, Scotland or Wales</option>
          <option value="ni">Northern Ireland</option>
        </Select>
        <Select
          label="Who gives notice?"
          value={giver}
          onChange={(e) => {
            setGiver(e.target.value as Giver);
            reset();
          }}
        >
          <option value="employer">The employer</option>
          <option value="employee">The employee or worker</option>
        </Select>
        <Select
          label="Employment status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as Status);
            reset();
          }}
        >
          <option value="employee">Employee</option>
          <option value="worker">Worker (not an employee)</option>
        </Select>
        <TextField
          label="Start date"
          type="date"
          clearable={false}
          value={startDate}
          onChange={(e) => {
            setStartDate(e.target.value);
            reset();
          }}
        />
        <TextField
          label="Date notice is given"
          type="date"
          clearable={false}
          value={noticeDate}
          onChange={(e) => {
            setNoticeDate(e.target.value);
            reset();
          }}
        />
        <TextField
          label="Contract notice (weeks)"
          type="number"
          inputMode="numeric"
          min={0}
          hint="Leave blank if the contract does not say."
          value={contractWeeks}
          onChange={(e) => {
            setContractWeeks(e.target.value);
            reset();
          }}
        />
        <Select
          label="Pay entered as"
          value={payMode}
          onChange={(e) => {
            setPayMode(e.target.value as PayMode);
            reset();
          }}
        >
          <option value="weekly">Average weekly pay (£)</option>
          <option value="annual">Annual salary (£)</option>
        </Select>
        <TextField
          label={payMode === "weekly" ? "Weekly pay (£)" : "Annual salary (£)"}
          type="number"
          inputMode="decimal"
          min={0}
          step="0.01"
          value={amount}
          onChange={(e) => {
            setAmount(e.target.value);
            reset();
          }}
        />
        <Select
          label="Arrangement during notice"
          value={arrangement}
          onChange={(e) => {
            setArrangement(e.target.value as Arrangement);
            reset();
          }}
        >
          <option value="work">Work the notice</option>
          <option value="garden-leave">Garden leave</option>
          <option value="pilon">Payment in lieu of notice (PILON)</option>
        </Select>
        <Button type="submit">Work out notice pay</Button>
      </form>
      <section
        aria-label="Notice result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-elevated rounded-control p-5 sm:p-6"
      >
        <NoticeOutput result={result} />
      </section>
    </div>
  );
}

function NoticeOutput({ result }: { result: ReturnType<typeof calculateNotice> | null }) {
  if (!result)
    return (
      <p className="text-callout text-label-secondary">
        Fill in the form, then work out notice pay.
      </p>
    );
  if (!result.ok) return <p className="text-callout text-label">{result.error}</p>;
  const r: NoticeResult = result;
  return (
    <>
      <h2 className="text-title-2 text-label">Your notice</h2>
      <dl className="text-callout text-label mt-4 space-y-3">
        <div>
          <dt className="font-semibold">Statutory notice</dt>
          <dd>{r.statutoryWeeks} weeks</dd>
        </div>
        <div>
          <dt className="font-semibold">Contractual notice</dt>
          <dd>{r.contractWeeks === null ? "Not stated" : `${r.contractWeeks} weeks`}</dd>
        </div>
        <div>
          <dt className="font-semibold">Notice that applies</dt>
          <dd>{r.noticeWeeks} weeks</dd>
        </div>
        <div>
          <dt className="font-semibold">Last day of notice</dt>
          <dd>{r.lastDay ?? "No notice period"}</dd>
        </div>
        <div>
          <dt className="font-semibold">Gross notice pay</dt>
          <dd>{gbp(r.noticePay)}</dd>
        </div>
      </dl>
      <h3 className="text-headline text-label mt-5">Workings</h3>
      <ul className="text-callout text-label-secondary mt-2 list-disc space-y-1 pl-5">
        {r.workings.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
      <h3 className="text-headline text-label mt-5">Notes</h3>
      <ul className="text-callout text-label-secondary mt-2 list-disc space-y-1 pl-5">
        {r.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </>
  );
}
