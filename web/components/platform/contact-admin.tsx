"use client";

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

import { PAGE_SIZE, Pager } from "./pager";

type Message = components["schemas"]["ContactMessageRow"];
type Filter = "" | "false" | "true";

/** Contact inbox: filter by handled, open a message, mark it handled or not handled. */
export function ContactAdmin() {
  const [filter, setFilter] = useState<Filter>("false");
  const [offset, setOffset] = useState(0);
  const [loaded, setRows] = useState<{ key: string; items: Message[]; total: number } | null>(null);
  const key = `${filter}:${offset}`;
  const rows = loaded?.key === key ? loaded.items : null;
  const [openId, setOpenId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  const fail = useCallback((p: Problem) => {
    if (p.code === "UNAUTHENTICATED" || p.code === "FORBIDDEN") {
      window.location.replace(`/session?next=${encodeURIComponent("/contact")}`);
      return;
    }
    setProblem(p);
  }, []);

  useEffect(() => {
    let live = true;
    void attempt((c) =>
      c.GET("/platform/contact-messages", {
        params: {
          query: { limit: PAGE_SIZE, offset, ...(filter ? { handled: filter === "true" } : {}) },
        },
      }),
    ).then((r) => {
      if (!live) return;
      if (r.ok) setRows({ key: `${filter}:${offset}`, items: r.data.items, total: r.data.total });
      else fail(r.problem);
    });
    return () => {
      live = false;
    };
  }, [filter, offset, fail]);

  async function mark(message: Message, handled: boolean) {
    const requestKey = key;
    const requestFilter = filter;
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.PATCH("/platform/contact-messages/{message_id}", {
        params: { path: { message_id: message.id } },
        body: { handled },
      }),
    );
    setBusy(false);
    if (!result.ok) return fail(result.problem);
    const updated = result.data;
    // Only touch the list the request was made from; a page or filter change moved on.
    setRows((current) => {
      if (!current || current.key !== requestKey) return current;
      let removed = 0;
      const items = current.items.flatMap((m) => {
        if (m.id !== message.id) return [m];
        // A message that no longer matches the filter leaves the list.
        const stays =
          requestFilter === "" || (requestFilter === "true") === (updated.handled_at !== null);
        if (!stays) removed += 1;
        return stays ? [updated] : [];
      });
      return { key: current.key, items, total: Math.max(0, current.total - removed) };
    });
  }

  return (
    <>
      <PageHeader
        title="Contact messages"
        description="Messages sent from the public contact form."
      />
      <Select
        label="Show"
        value={filter}
        onChange={(e) => {
          setOffset(0);
          setFilter(e.target.value as Filter);
        }}
        containerClassName="mb-6 max-w-xs"
      >
        <option value="false">Not handled</option>
        <option value="true">Handled</option>
        <option value="">All</option>
      </Select>
      {problem ? (
        <Alert tone="danger" title="That did not work" className="mb-6">
          {problem.message}
        </Alert>
      ) : null}
      {rows === null ? (
        <p className="text-callout text-label-secondary">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-callout text-label-secondary">No messages.</p>
      ) : (
        <ul className="grid gap-3" aria-label="Contact messages">
          {rows.map((m) => {
            const open = openId === m.id;
            const handled = m.handled_at !== null;
            return (
              <li key={m.id} className="bg-elevated rounded-card shadow-e1 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="text-callout min-w-0 break-words">
                    {m.name}
                    <span className="text-footnote text-label-secondary block break-all">
                      {m.email} · {m.topic} · {formatUk(m.created_at.slice(0, 10))}
                    </span>
                  </span>
                  <span className="flex items-center gap-3">
                    <StatusChip tone={handled ? "success" : "warning"}>
                      {handled ? "Handled" : "Not handled"}
                    </StatusChip>
                    <Button
                      variant="gray"
                      size="sm"
                      aria-expanded={open}
                      onClick={() => setOpenId(open ? null : m.id)}
                    >
                      {open ? "Close" : "Open"}
                    </Button>
                  </span>
                </div>
                {open ? (
                  <div className="mt-3">
                    {m.company ? (
                      <p className="text-footnote text-label-secondary mb-2">{m.company}</p>
                    ) : null}
                    <p className="text-callout whitespace-pre-wrap break-words">{m.message}</p>
                    <Button
                      className="mt-3"
                      variant="gray"
                      size="sm"
                      disabled={busy}
                      onClick={() => mark(m, !handled)}
                    >
                      {handled ? "Mark not handled" : "Mark handled"}
                    </Button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
      <Pager
        label="Contact messages"
        offset={offset}
        total={loaded?.total ?? 0}
        onChange={setOffset}
      />
    </>
  );
}
