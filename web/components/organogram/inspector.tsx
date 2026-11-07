"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";

import type { OrgPerson } from "./layout";

/** A person's summary, opened from the chart or the list (plan 5.6: the inspector drawer). */
export function PersonInspector({
  person,
  rtwVisible,
  onClose,
}: {
  person: OrgPerson | null;
  rtwVisible: boolean;
  onClose: () => void;
}) {
  return (
    <Sheet
      open={person !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      {person ? (
        <SheetContent
          title={person.name}
          description={
            [person.job_title, person.department].filter(Boolean).join(" · ") ||
            "Person in the org chart"
          }
          side="right"
          footer={
            <Button asChild variant="filled">
              <Link href={`/employees/${person.id}`}>Open employee record</Link>
            </Button>
          }
        >
          <dl className="text-callout grid grid-cols-[max-content_1fr] gap-x-6 gap-y-3">
            <dt className="text-label-secondary">Level</dt>
            <dd>{person.level ?? "Not set"}</dd>
            <dt className="text-label-secondary">Department</dt>
            <dd>{person.department ?? "Not set"}</dd>
            <dt className="text-label-secondary">Job title</dt>
            <dd>{person.job_title ?? "Not set"}</dd>
            <dt className="text-label-secondary">Direct reports</dt>
            <dd>{person.reports.length}</dd>
            {rtwVisible ? (
              <>
                <dt className="text-label-secondary">Right to work</dt>
                <dd>{person.rtw_status ? person.rtw_status.replace(/_/g, " ") : "Not set"}</dd>
              </>
            ) : null}
          </dl>
        </SheetContent>
      ) : null}
    </Sheet>
  );
}
