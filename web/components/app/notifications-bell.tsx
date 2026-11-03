"use client";

import { Bell, BellRing } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useCan, useMe } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button, IconButton } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip } from "@/components/ui/tooltip";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { sentTime } from "@/lib/compliance/reminders";

type Feed = components["schemas"]["NotificationPage"];

/** Live compliance actions are resolved at source; marking messages read never clears them. */
export function NotificationsBell({ count = 0 }: { count?: number }) {
  const me = useMe();
  const can = useCan();
  const pathname = usePathname();
  const identity = me?.active_company_id
    ? `${me.active_company_id}:${me.user.id}:${me.role}`
    : null;
  const [feed, setFeed] = useState<{ identity: string; data: Feed } | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const data = feed?.identity === identity ? feed?.data : undefined;
  useEffect(() => {
    let active = true;
    async function load() {
      if (!identity) return;
      const result = await attempt((c) => c.GET("/notifications"));
      if (!active) return;
      if (result.ok) {
        setFeed({ identity, data: result.data });
        setProblem(null);
      } else setProblem(result.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, [identity, pathname, open]);
  async function markAll() {
    if (!identity) return;
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) => c.POST("/notifications/read-all"));
    if (!result.ok) {
      setBusy(false);
      return setProblem(result.problem);
    }
    const refreshed = await attempt((c) => c.GET("/notifications"));
    setBusy(false);
    if (refreshed.ok) setFeed({ identity, data: refreshed.data });
    else setProblem(refreshed.problem);
  }
  async function read(id: string) {
    const result = await attempt((c) =>
      c.PATCH("/notifications/{notification_id}", {
        params: { path: { notification_id: id } },
        body: { read: true },
      }),
    );
    if (!result.ok) setProblem(result.problem);
  }
  async function more() {
    if (!identity || !data?.next_cursor) return;
    setBusy(true);
    const result = await attempt((c) =>
      c.GET("/notifications", { params: { query: { cursor: data.next_cursor } } }),
    );
    setBusy(false);
    if (result.ok)
      setFeed({ identity, data: { ...result.data, items: [...data.items, ...result.data.items] } });
    else setProblem(result.problem);
  }
  const badge = data ? data.unread + data.attention_count : count;
  const badgeText = badge > 99 ? "99+" : String(badge);
  const label = data
    ? [
        `Notifications${badge > 0 ? `, ${badgeText} total` : ""}`,
        ...(data.attention_count ? [`${data.attention_count} need attention`] : []),
        ...(data.unread ? [`${data.unread} unread`] : []),
      ].join(", ")
    : count > 0
      ? `Notifications, ${badgeText} total, ${count} unread`
      : "Notifications";
  const empty = !data || (data.attention_count === 0 && data.items.length === 0);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Tooltip content="Notifications">
        <PopoverTrigger asChild>
          <IconButton label={label} className="relative">
            <Icon icon={Bell} />
            {badge > 0 && (
              <span
                aria-hidden="true"
                className="bg-danger text-on-accent text-caption rounded-pill absolute top-1 right-1 min-w-4 px-1 text-center leading-4 font-semibold tabular-nums"
              >
                {badgeText}
              </span>
            )}
          </IconButton>
        </PopoverTrigger>
      </Tooltip>
      <PopoverContent
        label="Notifications"
        align="end"
        className="w-[22rem] max-h-[80dvh] overflow-y-auto p-0"
      >
        <div className="flex items-center justify-between gap-2 p-4 border-b border-separator">
          <h2 className="text-headline text-label">Notifications</h2>
          {!!data?.unread && (
            <Button size="sm" variant="plain" loading={busy} onClick={() => void markAll()}>
              Mark all read
            </Button>
          )}
        </div>
        {problem && (
          <div className="p-4">
            <Alert tone="danger" title={problem.message} />
          </div>
        )}
        {identity && !data && !problem ? (
          <p role="status" className="p-4 text-callout text-label-secondary">
            Loading notifications…
          </p>
        ) : empty && !problem ? (
          <EmptyState
            icon={BellRing}
            title="You're all caught up"
            description="Approvals, reminders and policies to sign will appear here."
            headingLevel={3}
            className="py-8"
          />
        ) : null}
        {data && can("compliance.overview.read") && (
          <section aria-label="Needs attention" className="p-4 border-b border-separator">
            <h3 className="text-caption text-label-secondary uppercase tracking-wider">
              Needs attention ({data.attention_count})
            </h3>
            <ul className="flex flex-col gap-3 mt-3">
              {data.needs_attention.map((item) => (
                <li key={item.id}>
                  <Link
                    href={item.href as Route}
                    onClick={() => setOpen(false)}
                    className="block text-callout text-accent-text underline"
                  >
                    <span className="font-semibold">{item.title}</span> · {item.detail}
                    <span className="block text-caption">{item.action}</span>
                  </Link>
                </li>
              ))}
            </ul>
            {data.attention_count === 0 && (
              <p className="text-callout text-label-secondary mt-2">No compliance actions due.</p>
            )}
            <Link
              href="/sponsor-compliance"
              onClick={() => setOpen(false)}
              className="inline-flex hit-target items-center text-callout text-accent-text underline mt-2"
            >
              View compliance hub
            </Link>
          </section>
        )}
        {data && data.items.length > 0 && (
          <section aria-label="Your messages" className="p-4">
            <h3 className="text-caption text-label-secondary uppercase tracking-wider">
              Your messages
            </h3>
            <ul className="mt-3 flex flex-col gap-4">
              {data.items.map((item) => (
                <li key={item.id}>
                  <p className="text-body text-label font-medium">
                    {item.title}
                    {!item.read_at && (
                      <span className="text-caption text-accent-text"> · Unread</span>
                    )}
                  </p>
                  <p className="text-caption text-label-secondary">
                    <time dateTime={item.created_at}>{sentTime(item.created_at)}</time>
                  </p>
                  {item.body && (
                    <p className="text-callout text-label-secondary whitespace-pre-wrap break-words mt-1">
                      {item.body}
                    </p>
                  )}
                  {item.link?.startsWith("/") && !item.link.startsWith("//") && (
                    <Link
                      href={item.link as Route}
                      className="text-callout text-accent-text underline inline-flex hit-target items-center"
                      onClick={() => {
                        void read(item.id);
                        setOpen(false);
                      }}
                    >
                      Open message<span className="sr-only"> · {item.title}</span>
                    </Link>
                  )}
                </li>
              ))}
            </ul>
            {data.next_cursor && (
              <Button variant="gray" className="mt-3" loading={busy} onClick={() => void more()}>
                More messages
              </Button>
            )}
          </section>
        )}
      </PopoverContent>
    </Popover>
  );
}
