"use client";

import { CircleHelp, Search } from "lucide-react";
import { usePathname } from "next/navigation";

import { IconButton } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Tooltip } from "@/components/ui/tooltip";
import { breadcrumbsFor, pageHrefFor, titleFor } from "@/lib/navigation";
import { keyLabel } from "@/lib/platform";
import { OPEN_PALETTE, OPEN_SHORTCUTS, announce } from "@/lib/shell-events";
import type { ThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/utils";

import { AvatarMenu } from "./avatar-menu";
import { Breadcrumbs } from "./breadcrumbs";
import { NotificationsBell } from "./notifications-bell";
import type { ShellUser } from "./shell-types";
import { useApple } from "./use-apple";
import { usePageHeading } from "./use-page-heading";
import { useScrolled } from "./use-scrolled";

interface ToolbarProps {
  user: ShellUser | null;
  theme: ThemeChoice;
  notificationCount: number;
}

/**
 * The translucent toolbar (plan 5.6), 56 px and sticky: breadcrumbs and the page title on the left,
 * search in the middle, then help, notifications and the account menu.
 */
export function Toolbar({ user, theme, notificationCount }: ToolbarProps) {
  const pathname = usePathname();
  const heading = usePageHeading(pathname);
  const title = heading.title || titleFor(pathname);
  const crumbs = breadcrumbsFor(pathname);
  if (heading.title && heading.title !== titleFor(pathname) && pageHrefFor(pathname) !== pathname) {
    const parent = crumbs.at(-1);
    // The page this one was opened from. Cutting the last part off the address is not enough:
    // /learning/assignments has no page of its own, and a link to nowhere is fetched for ever.
    if (parent) parent.href = pageHrefFor(pathname);
    crumbs.push({ label: heading.title });
  }
  const apple = useApple();
  const scrolled = useScrolled();
  const hint = apple ? "⌘K" : `${keyLabel("Mod", false)} K`;
  return (
    <header
      data-scrolled={scrolled}
      className={cn(
        // Floating, 12 px from the edges (below the notch on phones). Clear at the top of the page;
        // glass once content scrolls under it (U6.1.3).
        "rounded-card sticky top-[max(0.75rem,env(safe-area-inset-top))] z-20 mx-3 mt-3 flex h-14 items-center gap-3 px-4 md:mx-0 md:mr-3 md:px-5",
        scrolled ? "material-glass-regular" : "bg-transparent",
      )}
    >
      <div className="min-w-0 flex-1 lg:flex-none lg:basis-80">
        <Breadcrumbs crumbs={crumbs} />
        {title ? (
          <p
            title={title}
            aria-hidden={heading.visible}
            className={`text-title-2 text-label truncate leading-7 transition-opacity motion-reduce:transition-none ${heading.visible ? "opacity-0" : "opacity-100"}`}
          >
            {title}
          </p>
        ) : null}
      </div>

      <div className="hidden min-w-0 flex-1 justify-center lg:flex">
        <button
          type="button"
          onClick={() => announce(OPEN_PALETTE)}
          className="bg-fill-secondary rounded-pill text-body text-placeholder hover:bg-label/10 flex h-9 w-full max-w-md cursor-pointer items-center gap-2 px-3 text-left transition-colors motion-micro"
        >
          <Icon icon={Search} size={16} className="text-label-secondary" />
          <span className="flex-1">Search</span>
          <kbd className="text-footnote text-label-secondary bg-elevated rounded-control px-1.5 py-0.5 font-sans">
            {hint}
          </kbd>
        </button>
      </div>

      <div className="flex items-center gap-0.5">
        <IconButton
          label="Search"
          size="sm"
          className="lg:hidden"
          onClick={() => announce(OPEN_PALETTE)}
        >
          <Icon icon={Search} />
        </IconButton>
        <Tooltip content="Help and shortcuts">
          <IconButton
            label="Help and keyboard shortcuts"
            size="sm"
            onClick={() => announce(OPEN_SHORTCUTS)}
          >
            <Icon icon={CircleHelp} />
          </IconButton>
        </Tooltip>
        <NotificationsBell count={notificationCount} />
        <AvatarMenu user={user} theme={theme} />
      </div>
    </header>
  );
}
