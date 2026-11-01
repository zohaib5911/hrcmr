"use client";

import { Check, ChevronsUpDown } from "lucide-react";

import { Avatar } from "@/components/ui/avatar";
import { Icon } from "@/components/ui/icon";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuTrigger } from "@/components/ui/menu";
import { SkeletonPerson } from "@/components/ui/skeleton";
import { StatusChip } from "@/components/ui/status-chip";
import { cn } from "@/lib/utils";

import { PLAN_LABELS, type ShellSession } from "./shell-types";

/** The company at the top of the sidebar: logo, name and plan, and a menu to switch (plan 5.6). */
export function CompanySwitcher({ session }: { session: ShellSession | null }) {
  if (!session) {
    return (
      <div className="px-4 py-4">
        <SkeletonPerson />
      </div>
    );
  }
  const { company, companies } = session;
  return (
    <div className="px-3 py-3">
      <Menu>
        <MenuTrigger asChild>
          <button
            type="button"
            className={cn(
              "rounded-control hover:bg-fill-secondary flex w-full cursor-pointer items-center gap-3 p-2 text-left transition-colors motion-micro",
              "group-data-[collapsed=true]/shell:justify-center",
            )}
          >
            <Avatar name={company.name} size="md" decorative />
            <span className="min-w-0 flex-1 group-data-[collapsed=true]/shell:sr-only">
              <span className="text-headline text-label block truncate">{company.name}</span>
              <StatusChip tone={company.plan === "free" ? "neutral" : "info"} className="mt-0.5">
                {PLAN_LABELS[company.plan]}
              </StatusChip>
            </span>
            <Icon
              icon={ChevronsUpDown}
              size={16}
              className="text-label-secondary shrink-0 group-data-[collapsed=true]/shell:hidden"
            />
            <span className="sr-only group-data-[collapsed=false]/shell:hidden">
              , switch company
            </span>
          </button>
        </MenuTrigger>
        <MenuContent align="start">
          <MenuLabel>Your companies</MenuLabel>
          {companies.map((other) => (
            <MenuItem
              key={other.id}
              disabled={other.id !== company.id}
              icon={
                other.id === company.id ? (
                  <Icon icon={Check} size={16} />
                ) : (
                  <span className="size-4" />
                )
              }
            >
              {other.name}
            </MenuItem>
          ))}
        </MenuContent>
      </Menu>
    </div>
  );
}
