"use client";

import {
  BadgeCheck,
  Banknote,
  Calendar,
  Building2,
  CalendarDays,
  Clock,
  CreditCard,
  FileCheck2,
  FileText,
  Landmark,
  MapPin,
  Percent,
  ShieldCheck,
  Trash2,
  Users,
  Wallet,
} from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { StatusChip } from "@/components/ui/status-chip";
import { GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { Icon } from "@/components/ui/icon";
import { CARD_VARIANTS } from "@/components/ui/card";
import { PLAN_LABELS } from "@/components/app/shell-types";
import { useCan } from "@/components/app/session-context";
import type { components } from "@/lib/api/client";
import { companyLine } from "@/lib/company/details";
import { cn } from "@/lib/utils";

import { DetailsSheet } from "./details-sheet";
import { LogoPicture } from "./logo-picture";

type Overview = components["schemas"]["CompanyOverview"];
type Options = components["schemas"]["CompanyOptions"];

const PLAN = { free: "free", annual: "annual", ten_year: "ten-year" } as const;

/** `/company` (plan 8.15): the company card, then grouped rows that lead to each part of its set-up. */
export function CompanyOverview({
  overview,
  options,
}: {
  overview: Overview;
  options: Options | null;
}) {
  const {
    company,
    features,
    users,
    locations,
    departments,
    designations,
    key_personnel_roles,
    compliance_documents,
  } = overview;
  const can = useCan();
  const [editing, setEditing] = useState(false);
  const mayEdit = can("company.profile.write") && options !== null;

  return (
    <>
      <PageHeader title="Company" description="Your company's details, and how it is set up." />
      <div className="flex flex-col gap-8">
        <section
          aria-label="Your company"
          className={cn(CARD_VARIANTS.glass, "flex items-center gap-4 p-5")}
        >
          <LogoPicture name={company.name} hasLogo={company.has_logo} size="lg" />
          <div className="min-w-0 flex-1">
            <p className="text-title-3 text-label truncate">{company.name}</p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <StatusChip tone={company.status === "active" ? "success" : "warning"}>
                {company.status === "active" ? "Active" : "Not active"}
              </StatusChip>
              <StatusChip tone={company.plan === "free" ? "neutral" : "info"}>
                {PLAN_LABELS[PLAN[company.plan]]} plan
              </StatusChip>
            </div>
          </div>
        </section>

        <GroupedList heading="Company">
          <GroupedRow
            title="Details"
            detail={companyLine(company)}
            icon={<Icon icon={FileText} />}
            {...(mayEdit ? { onClick: () => setEditing(true) } : {})}
          />
          {can("company.location.read") ? (
            <GroupedRow
              title="Locations"
              detail={String(locations)}
              icon={<Icon icon={MapPin} />}
              href="/company/locations"
            />
          ) : null}
          {can("company.department.read") ? (
            <GroupedRow
              title="Departments"
              detail={String(departments)}
              icon={<Icon icon={Building2} />}
              href="/company/departments"
            />
          ) : null}
          {can("settings.designation.read") ? (
            <GroupedRow
              title="Designations"
              detail={String(designations)}
              icon={<Icon icon={BadgeCheck} />}
              href="/company/designations"
            />
          ) : null}
          {can("company.profile.read") ? (
            <GroupedRow
              title="Key personnel"
              detail={`${key_personnel_roles} of 4`}
              icon={<Icon icon={ShieldCheck} />}
              href="/company/key-personnel"
            />
          ) : null}
          {can("company.profile.read") ? (
            <GroupedRow
              title="Compliance documents"
              detail={`${compliance_documents} of 18`}
              icon={<Icon icon={FileCheck2} />}
              href="/company/compliance-documents"
            />
          ) : null}
        </GroupedList>

        <GroupedList heading="Time">
          {can("holiday.calendar.read") ? (
            <GroupedRow
              title="Working pattern"
              icon={<Icon icon={CalendarDays} />}
              href="/company/working-pattern"
            />
          ) : null}
          {can("holiday.calendar.read") ? (
            <GroupedRow
              title="Holidays and closures"
              icon={<Icon icon={CalendarDays} />}
              href="/holiday-management"
            />
          ) : null}
          {can("company.profile.read") ? (
            <GroupedRow
              title="Trading hours"
              icon={<Icon icon={Clock} />}
              href="/company/trading-hours"
            />
          ) : null}
        </GroupedList>

        <GroupedList heading="Pay">
          {can("company.profile.read") ? (
            <GroupedRow
              title="Bank accounts"
              icon={<Icon icon={Landmark} />}
              href="/company/bank-accounts"
            />
          ) : null}
          {can("settings.tax_code.read") ? (
            <GroupedRow
              title="Tax codes"
              icon={<Icon icon={Percent} />}
              href="/company/tax-codes"
            />
          ) : null}
          {can("settings.payment_type.read") ? (
            <GroupedRow
              title="Payment types"
              icon={<Icon icon={Wallet} />}
              href="/company/payment-types"
            />
          ) : null}
          {can("settings.pay_band.read") ? (
            <GroupedRow
              title="Pay bands"
              icon={<Icon icon={Banknote} />}
              href="/company/pay-bands"
            />
          ) : null}
          {can("settings.pay_schedule.read") ? (
            <GroupedRow
              title="Pay schedules"
              icon={<Icon icon={Calendar} />}
              href="/company/pay-schedules"
            />
          ) : null}
        </GroupedList>

        <GroupedList heading="Access and billing">
          <GroupedRow
            title="User access"
            detail={`${users} ${users === 1 ? "person" : "people"}`}
            icon={<Icon icon={Users} />}
            href="/company/users"
          />
          <GroupedRow
            title="Billing"
            detail={`${PLAN_LABELS[PLAN[company.plan]]} plan`}
            icon={<Icon icon={CreditCard} />}
            href="/company/billing"
          />
          {can("company.delete") ? (
            <GroupedRow
              title="Delete company account"
              icon={<Icon icon={Trash2} />}
              href="/company/delete-account"
            />
          ) : null}
        </GroupedList>
      </div>

      {options ? (
        <DetailsSheet
          open={editing}
          onOpenChange={setEditing}
          company={company}
          features={features}
          options={options}
        />
      ) : null}
    </>
  );
}
