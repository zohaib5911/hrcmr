"use client";

import { Ellipsis } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Icon } from "@/components/ui/icon";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { MOBILE_TABS, NAV_GROUPS, findNavItem, isActive } from "@/lib/navigation";
import { cn } from "@/lib/utils";

const TAB =
  "text-caption flex min-h-14 w-full flex-col items-center justify-center gap-0.5 font-medium transition-colors motion-micro";

/**
 * On phones the sidebar becomes a bottom tab bar: Home, People, Compliance, Time and Me, with a
 * "More" sheet for everything else (plan 5.6). Every target is at least 44 px.
 */
export function MobileTabBar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const group = findNavItem(pathname)?.group;
  const inTabs = MOBILE_TABS.some((tab) => group && tab.groups.includes(group));

  return (
    <nav
      aria-label="Primary"
      className="material-chrome border-separator fixed inset-x-0 bottom-0 z-30 border-t pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      <ul className="grid grid-cols-6">
        {MOBILE_TABS.map((tab) => {
          const current = group !== undefined && tab.groups.includes(group);
          return (
            <li key={tab.label}>
              <Link
                href={tab.href as Route}
                aria-current={current ? "true" : undefined}
                className={cn(TAB, current ? "text-accent-text" : "text-label-secondary")}
              >
                <Icon icon={tab.icon} />
                {tab.label}
              </Link>
            </li>
          );
        })}
        <li>
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <button
                type="button"
                aria-current={group !== undefined && !inTabs ? "true" : undefined}
                className={cn(
                  TAB,
                  "cursor-pointer",
                  group !== undefined && !inTabs ? "text-accent-text" : "text-label-secondary",
                )}
              >
                <Icon icon={Ellipsis} />
                More
              </button>
            </SheetTrigger>
            <SheetContent title="More" description="Everywhere in the app.">
              <nav aria-label="All pages" className="flex flex-col gap-4 pb-2">
                {NAV_GROUPS.map((g) => (
                  <section key={g.id} aria-labelledby={`more-${g.id}`}>
                    <h3
                      id={`more-${g.id}`}
                      className="text-caption text-label-secondary px-2 pb-1 font-medium tracking-wider uppercase"
                    >
                      {g.label}
                    </h3>
                    <ul>
                      {g.items.map((item) => (
                        <li key={item.id}>
                          <Link
                            href={item.href as Route}
                            onClick={() => setOpen(false)}
                            aria-current={isActive(item, pathname) ? "page" : undefined}
                            className={cn(
                              "rounded-control text-body hit-target flex items-center gap-3 px-2 py-2.5 font-medium",
                              isActive(item, pathname)
                                ? "bg-accent-tint text-accent-text"
                                : "text-label",
                            )}
                          >
                            <Icon icon={item.icon} />
                            {item.label}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
        </li>
      </ul>
    </nav>
  );
}
