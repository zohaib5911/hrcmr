"use client";

import { CalendarDays } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export function LeaveHome() {
  const can = useCan();
  return (
    <>
      <PageHeader
        title="Leave"
        description="Requests, approvals and balances."
        actions={
          can("leave.config.read") ? (
            <Button asChild variant="gray">
              <Link href="/leave/settings">Leave settings</Link>
            </Button>
          ) : null
        }
      />
      <div className="bg-elevated rounded-card shadow-e1">
        <EmptyState
          icon={CalendarDays}
          title="No leave booked yet"
          description="Requests, approvals and balances will appear here, with bank holidays taken into account."
        />
      </div>
    </>
  );
}
