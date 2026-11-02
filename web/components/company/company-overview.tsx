"use client";

import { CreditCard, FileText, Users } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { StatusChip } from "@/components/ui/status-chip";
import { GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { Icon } from "@/components/ui/icon";
import { PLAN_LABELS } from "@/components/app/shell-types";
import { useCan } from "@/components/app/session-context";
import type { components } from "@/lib/api/client";
import { companyLine } from "@/lib/company/details";

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
  const { company, features, users } = overview;
  const can = useCan();
  const [editing, setEditing] = useState(false);
  const mayEdit = can("company.profile.write") && options !== null;

  return (
    <>
      <PageHeader title="Company" description="Your company's details, and how it is set up." />
      <div className="flex flex-col gap-8">
        <section
          aria-label="Your company"
          className="bg-elevated rounded-card shadow-e1 flex items-center gap-4 p-5"
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
