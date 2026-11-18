"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import { useRouter } from "next/navigation";

import { BrandLogo } from "@/components/brand-logo";

import { Avatar } from "@/components/ui/avatar";
import { Icon } from "@/components/ui/icon";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuTrigger } from "@/components/ui/menu";
import { SkeletonPerson } from "@/components/ui/skeleton";
import { attempt } from "@/lib/auth/request";
import { cn } from "@/lib/utils";

import { PLAN_LABELS, type ShellSession } from "./shell-types";
import { clearApiCache } from "@/lib/api/cache";

/** The company at the top of the sidebar: logo, name and plan, and a menu to switch (plan 5.6). */
export function CompanySwitcher({ session }: { session: ShellSession | null }) {
  const router = useRouter();
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
      <div className="mb-2 flex justify-center group-data-[collapsed=true]/shell:hidden">
        <BrandLogo />
      </div>
      <div className="mb-2 hidden justify-center group-data-[collapsed=true]/shell:flex">
        <BrandLogo variant="mark" />
      </div>
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
              <span className="bg-accent-tint text-accent-text rounded-pill text-footnote mt-0.5 inline-flex px-2.5 py-0.5 font-medium">
                {PLAN_LABELS[company.plan]}
              </span>
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
              onSelect={() => {
                if (other.id === company.id) return;
                void attempt((client) =>
                  client.POST("/auth/switch-company", { body: { company_id: other.id } }),
                ).then((outcome) => {
                  if (!outcome.ok) return;
                  clearApiCache();
                  router.refresh();
                });
              }}
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
