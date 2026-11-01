"use client";

import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { IconButton } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Tooltip } from "@/components/ui/tooltip";
import { NAV_GROUPS, isActive, type NavItem } from "@/lib/navigation";
import { cn } from "@/lib/utils";

import { CompanySwitcher } from "./company-switcher";
import type { ShellSession } from "./shell-types";
import { UserCard } from "./user-card";

interface NavLinkProps {
  item: NavItem;
  active: boolean;
  badge?: number | undefined;
}

/** One sidebar row. Icon, label, and a count where there is something to count. */
export function NavLink({ item, active, badge }: NavLinkProps) {
  return (
    <Link
      // Navigation addresses come from one list (lib/navigation.ts), which a test checks against the pages.
      href={item.href as Route}
      aria-current={active ? "page" : undefined}
      className={cn(
        "rounded-control text-callout hit-target flex items-center gap-3 px-3 py-2 font-medium transition-colors motion-micro",
        "group-data-[collapsed=true]/shell:justify-center group-data-[collapsed=true]/shell:px-0",
        active ? "bg-accent-tint text-accent-text" : "text-label hover:bg-fill-secondary",
      )}
    >
      <Icon icon={item.icon} className="shrink-0" />
      <span className="min-w-0 flex-1 truncate group-data-[collapsed=true]/shell:sr-only">
        {item.label}
      </span>
      {badge ? (
        <>
          <span
            aria-hidden="true"
            className="bg-accent text-on-accent text-caption rounded-pill min-w-5 px-1.5 text-center font-semibold tabular-nums group-data-[collapsed=true]/shell:hidden"
          >
            {badge}
          </span>
          <span className="sr-only">, {badge} waiting</span>
        </>
      ) : null}
    </Link>
  );
}

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  session: ShellSession | null;
  badges: Readonly<Record<string, number>>;
}

/**
 * The translucent sidebar (plan 5.6): 260 px wide, 72 px when collapsed (the `[` key), grouped with
 * small-caps captions. The company is at the top and the person at the bottom. Phones do not show
 * it: they get the tab bar.
 */
export function Sidebar({ collapsed, onToggle, session, badges }: SidebarProps) {
  const pathname = usePathname();
  return (
    <aside
      id="app-sidebar"
      className={cn(
        "material-chrome border-separator fixed inset-y-0 left-0 z-30 hidden flex-col border-r md:flex",
        "w-[260px] group-data-[collapsed=true]/shell:w-[72px] transition-[width] motion-sheet motion-reduce:transition-none",
      )}
    >
      <CompanySwitcher session={session} />
      <nav aria-label="Main" className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-3 pb-3">
        {NAV_GROUPS.map((group) => (
          <div key={group.id} className="pt-3">
            <h2 className="text-caption text-label-secondary px-3 pb-1 font-medium tracking-wider uppercase group-data-[collapsed=true]/shell:sr-only">
              {group.label}
            </h2>
            <ul className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const link = (
                  <NavLink item={item} active={isActive(item, pathname)} badge={badges[item.id]} />
                );
                return (
                  <li key={item.id}>
                    {collapsed ? (
                      <Tooltip content={item.label} side="right">
                        {link}
                      </Tooltip>
                    ) : (
                      link
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-separator flex flex-col gap-1 border-t p-3">
        <UserCard user={session?.user ?? null} />
        <Tooltip
          content={collapsed ? "Expand sidebar ( [ )" : "Collapse sidebar ( [ )"}
          side="right"
        >
          <IconButton
            label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            size="sm"
            variant="plain"
            aria-expanded={!collapsed}
            aria-controls="app-sidebar"
            onClick={onToggle}
            className="self-end group-data-[collapsed=true]/shell:self-center"
          >
            <Icon icon={collapsed ? PanelLeftOpen : PanelLeftClose} />
          </IconButton>
        </Tooltip>
      </div>
    </aside>
  );
}
