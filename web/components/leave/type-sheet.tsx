"use client";

import { useState } from "react";

import { PaySheet } from "@/components/company/pay-sheet";
import { NumberField } from "@/components/ui/number-field";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { Toggle } from "@/components/ui/toggle";
import type { ApiClient, components } from "@/lib/api/client";
import { COLOURS } from "@/lib/company/holidays";

import type { LeaveType } from "./settings-page";

type Input = components["schemas"]["LeaveTypeIn"];

export function LeaveTypeSheet({ item, onClose }: { item: LeaveType | null; onClose: () => void }) {
  const [name, setName] = useState(item?.name ?? "");
  const [bankIncluded, setBankIncluded] = useState(item?.bank_holidays_included ?? false);
  const [paid, setPaid] = useState(item?.is_paid ?? true);
  const [statutory, setStatutory] = useState(item?.counts_toward_statutory ?? false);
  const [days, setDays] = useState<number | null>(
    item?.days_per_year == null ? null : Number(item.days_per_year),
  );
  const [carry, setCarry] = useState<number | null>(Number(item?.carry_over_limit_days ?? 0));
  const [accrual, setAccrual] = useState<Input["accrual_method"]>(
    item?.accrual_method ?? "front_loaded",
  );
  const [approval, setApproval] = useState(item?.requires_approval ?? true);
  const [colour, setColour] = useState<LeaveType["colour"]>(item?.colour ?? "blue");
  const [rule, setRule] = useState(item?.rule_text ?? "");
  const body = {
    name,
    is_paid: paid,
    bank_holidays_included: bankIncluded,
    counts_toward_statutory: statutory,
    days_per_year: days === null ? null : days.toFixed(2),
    carry_over_limit_days: (carry ?? 0).toFixed(2),
    accrual_method: accrual,
    requires_approval: approval,
    colour,
    rule_text: rule,
  };
  return (
    <PaySheet
      noun="Leave type"
      title={item ? `Edit ${item.name}` : "Add leave type"}
      existing={!!item}
      validate={() => {
        const errors: Record<string, string> = {};
        if (!name.trim()) errors.name = "Enter a leave type name.";
        if (days !== null && days < 0) errors.days_per_year = "Use zero or more days.";
        if (carry === null || carry < 0)
          errors.carry_over_limit_days = "Enter a carry-over limit of zero or more days.";
        return Object.keys(errors).length ? errors : null;
      }}
      save={(api) =>
        item
          ? api.PATCH("/leave/types/{type_id}", { params: { path: { type_id: item.id } }, body })
          : api.POST("/leave/types", { body })
      }
      {...(item
        ? {
            remove: (api: ApiClient) =>
              api.DELETE("/leave/types/{type_id}", { params: { path: { type_id: item.id } } }),
          }
        : {})}
      archiveDetail="This type is hidden for future use. Its history is kept."
      onClose={onClose}
    >
      {(errors) => (
        <>
          <TextField
            label="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            error={errors.name}
            maxLength={80}
          />
          <Toggle
            label="Paid provision"
            checked={paid}
            onCheckedChange={setPaid}
            description="Subject to eligibility and company policy; not a guarantee of full pay."
          />
          <Toggle
            label="Counts toward statutory annual leave minimum"
            checked={statutory}
            onCheckedChange={setStatutory}
          />
          <Toggle
            label="Bank holidays included in allowance"
            checked={bankIncluded}
            onCheckedChange={setBankIncluded}
            description="Deduct bank holidays that fall on the employee’s working days when the company treats them as non-working."
          />
          <NumberField
            label="Days a year"
            hint="Leave blank for no fixed annual allowance."
            value={days}
            onChange={setDays}
            decimals={2}
            step={0.5}
            min={0}
            max={9999.99}
            error={errors.days_per_year}
          />
          <NumberField
            label="Carry-over limit (days)"
            hint="Company policy. Protected statutory carry-over may require more."
            value={carry}
            onChange={setCarry}
            decimals={2}
            step={0.5}
            min={0}
            max={9999.99}
            error={errors.carry_over_limit_days}
          />
          <Select
            label="Accrual method"
            value={accrual}
            onChange={(event) => setAccrual(event.target.value as Input["accrual_method"])}
          >
            <option value="front_loaded">Front loaded</option>
            <option value="monthly">Monthly</option>
          </Select>
          <Toggle label="Requires approval" checked={approval} onCheckedChange={setApproval} />
          <Select
            label="Colour"
            value={colour}
            onChange={(event) => setColour(event.target.value as LeaveType["colour"])}
          >
            {COLOURS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          <TextArea
            label="Rule text"
            value={rule}
            onChange={(event) => setRule(event.target.value)}
            maxLength={4000}
            error={errors.rule_text}
          />
          {item?.source_url ? (
            <p className="text-footnote text-label-secondary">
              Original seed reference:{" "}
              <a
                className="text-accent-text underline"
                href={item.source_url}
                target="_blank"
                rel="noreferrer"
              >
                GOV.UK
              </a>
              , checked {item.checked_on}. Changes here are your company policy.
            </p>
          ) : null}
        </>
      )}
    </PaySheet>
  );
}
