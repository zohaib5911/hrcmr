"use client";

import { Bell, BellRing } from "lucide-react";

import { IconButton } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip } from "@/components/ui/tooltip";

/** The bell (plan 5.6). The notifications themselves arrive with T14.2; until then there are none. */
export function NotificationsBell({ count = 0 }: { count?: number }) {
  return (
    <Popover>
      <Tooltip content="Notifications">
        <PopoverTrigger asChild>
          <IconButton
            label={count > 0 ? `Notifications, ${count} unread` : "Notifications"}
            className="relative"
          >
            <Icon icon={Bell} />
            {count > 0 ? (
              <span
                aria-hidden="true"
                className="bg-danger text-on-accent text-caption rounded-pill absolute top-1 right-1 min-w-4 px-1 text-center leading-4 font-semibold tabular-nums"
              >
                {count > 99 ? "99+" : count}
              </span>
            ) : null}
          </IconButton>
        </PopoverTrigger>
      </Tooltip>
      <PopoverContent label="Notifications" align="end" className="w-[22rem] p-0">
        <EmptyState
          icon={BellRing}
          title="You're all caught up"
          description="Approvals, reminders and policies to sign will appear here."
          headingLevel={3}
          className="py-8"
        />
      </PopoverContent>
    </Popover>
  );
}
