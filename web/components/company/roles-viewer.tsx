"use client";

import { ShieldCheck } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Select } from "@/components/ui/select";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import type { components } from "@/lib/api/client";
import { ROLE_LABELS } from "@/lib/auth/roles";
import { ROLE_DESCRIPTIONS } from "@/lib/company/access";

type Matrix = components["schemas"]["RoleMatrix"];

/** "What can each role do?" (plan 8.15): pick a role, read everything it can do, grouped by area. */
export function RolesViewer({ matrix }: { matrix: Matrix }) {
  const [role, setRole] = useState<keyof typeof ROLE_LABELS>("company_admin");
  const summary = matrix.roles.find((r) => r.role === role);
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="gray">
          <Icon icon={ShieldCheck} />
          What can each role do?
        </Button>
      </SheetTrigger>
      <SheetContent
        title="What can each role do?"
        description="Generated from the same list the system enforces."
        readOnly
      >
        <div className="flex flex-col gap-4 pb-4">
          <Select
            label="Role"
            value={role}
            onChange={(e) => setRole(e.target.value as keyof typeof ROLE_LABELS)}
          >
            {matrix.roles.map((r) => (
              <option key={r.role} value={r.role}>
                {ROLE_LABELS[r.role]}
              </option>
            ))}
          </Select>
          <p className="text-callout text-label-secondary">{ROLE_DESCRIPTIONS[role]}</p>
          {summary?.groups.map((group) => (
            <section key={group.area} aria-label={group.label}>
              <h3 className="text-headline text-label">{group.label}</h3>
              <ul className="text-callout text-label-secondary mt-1 list-disc pl-5">
                {group.items.map((item) => (
                  <li key={item.permission}>{item.label}</li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}
