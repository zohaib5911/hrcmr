"use client";

import { CircleHelp, Search } from "lucide-react";
import { usePathname } from "next/navigation";

import { IconButton } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Tooltip } from "@/components/ui/tooltip";
import { breadcrumbsFor, findNavItem } from "@/lib/navigation";
import { keyLabel } from "@/lib/platform";
import { OPEN_PALETTE, OPEN_SHORTCUTS, announce } from "@/lib/shell-events";
import type { ThemeChoice } from "@/lib/theme";

import { AvatarMenu } from "./avatar-menu";
import { Breadcrumbs } from "./breadcrumbs";
import { NotificationsBell } from "./notifications-bell";
import type { ShellUser } from "./shell-types";
import { useApple } from "./use-apple";

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
  const item = findNavItem(pathname);
  const apple = useApple();
  const hint = apple ? "⌘K" : `${keyLabel("Mod", false)} K`;
  return (
    <header className="material-chrome border-separator sticky top-0 z-20 flex h-14 items-center gap-3 border-b px-4 md:px-8">
      <div className="min-w-0 flex-1 lg:flex-none lg:basis-80">
        <Breadcrumbs crumbs={breadcrumbsFor(pathname)} />
        {item ? <p className="text-title-3 text-label truncate leading-6">{item.label}</p> : null}
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
