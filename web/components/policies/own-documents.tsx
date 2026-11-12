"use client";

import { ScrollText } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import { attempt, baseUrl, type Problem } from "@/lib/auth/request";
import { formatUk, formatUkDateTime } from "@/lib/ui/dates";

import { ACCEPTANCE_STATUS, VIEWABLE_MIME, type OwnPolicy, type PolicyReceipt } from "./labels";

/** My Documents: policies to read, with the viewer, accept or sign, and the receipt afterwards. */
export function OwnPolicies() {
  const can = useCan();
  const mayRead = can("policy.acceptance.read_own");
  const [items, setItems] = useState<OwnPolicy[] | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    if (!mayRead) return;
    let active = true;
    void attempt((c) => c.GET("/policies/own")).then((result) => {
      if (!active) return;
      if (result.ok) setItems(result.data.items);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [mayRead]);

  if (!mayRead) return null;
  if (problem) return <Alert tone="danger" title={problem.message} />;
  if (items === null)
    return <p className="text-callout text-label-secondary">Loading your policies…</p>;

  return (
    <section aria-labelledby="my-policies" className="flex flex-col gap-4">
      <h2 id="my-policies" className="text-title-3 text-label font-semibold">
        Policies to read and confirm
      </h2>
      {items.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          headingLevel={3}
          title="Nothing to read right now"
          description="Policies HR asks you to read or sign will appear here, with your receipt once you have."
        />
      ) : (
        items.map((item) => (
          <PolicyCard
            key={item.id}
            item={item}
            onConfirmed={(next) =>
              setItems((rows) => rows?.map((row) => (row.id === next.id ? next : row)) ?? rows)
            }
          />
        ))
      )}
    </section>
  );
}

function PolicyCard({
  item,
  onConfirmed,
}: {
  item: OwnPolicy;
  onConfirmed: (next: OwnPolicy) => void;
}) {
  const [receipt, setReceipt] = useState<PolicyReceipt | null>(null);
  const [showReceipt, setShowReceipt] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const done = item.accepted_at !== null;
  const signing = item.confirmation_mode === "sign";
  const viewable = (VIEWABLE_MIME as readonly string[]).includes(item.file_mime);
  const status = ACCEPTANCE_STATUS[item.status];

  async function confirm(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!confirmed)
      return setProblem({
        code: "VALIDATION_ERROR",
        message: signing
          ? "Tick the box to say you have read this document."
          : "Tick the box to say you have read and accept this document.",
        field: "confirmed",
      } as Problem);
    if (signing && !typed.trim())
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Type your full name to sign.",
        field: "typed_signature",
      } as Problem);
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/policies/{policy_id}/accept", {
        params: { path: { policy_id: item.id } },
        body: signing ? { confirmed: true, typed_signature: typed.trim() } : { confirmed: true },
      }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    setReceipt(result.data);
    onConfirmed({
      ...item,
      accepted_at: result.data.accepted_at,
      status: signing ? "signed" : "accepted",
    });
  }

  async function loadReceipt() {
    setShowReceipt(true);
    if (receipt) return;
    const result = await attempt((c) =>
      c.GET("/policies/{policy_id}/receipt", { params: { path: { policy_id: item.id } } }),
    );
    if (result.ok) setReceipt(result.data);
    else setProblem(result.problem);
  }

  async function download() {
    const result = await attempt((c) =>
      c.GET("/policies/own/{policy_id}/download", { params: { path: { policy_id: item.id } } }),
    );
    if (!result.ok) return setProblem(result.problem);
    window.open(result.data.url, "_blank", "noopener,noreferrer");
  }

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-headline text-label break-words">{item.title}</h3>
          <p className="text-footnote text-label-secondary">
            Version {item.version}
            {done
              ? ` · ${signing ? "Signed" : "Accepted"} ${formatUk(item.accepted_at!.slice(0, 10))}`
              : ` · Due ${formatUk(item.due_on)}`}
          </p>
        </div>
        <StatusChip tone={status.tone}>{status.label}</StatusChip>
      </div>

      {viewable ? (
        <iframe
          title={`${item.title}, version ${item.version}`}
          src={`${baseUrl()}/policies/own/${item.id}/view`}
          className="h-96 w-full rounded-lg border border-separator bg-fill-secondary"
        />
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-callout text-label-secondary">This file opens in another app.</p>
          <Button variant="gray" size="sm" onClick={() => void download()}>
            Download to read
          </Button>
        </div>
      )}

      {problem && <Alert tone="danger" title={problem.message} />}

      {!done && (
        <form onSubmit={(e) => void confirm(e)} className="flex flex-col gap-3" noValidate>
          <Checkbox
            label={signing ? "I have read this document." : "I have read and accept this document."}
            checked={confirmed}
            onCheckedChange={(value) => setConfirmed(value === true)}
          />
          {signing && (
            <TextField
              label="Type your full name to sign"
              autoComplete="name"
              maxLength={200}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              hint="Your name is kept with a timestamp and your IP address."
            />
          )}
          <div>
            <Button type="submit" variant="filled" disabled={busy}>
              {signing ? "Sign and confirm" : "I have read and accept"}
            </Button>
          </div>
        </form>
      )}

      {done && (
        <div className="flex flex-col gap-3">
          {!showReceipt ? (
            <div>
              <Button variant="gray" size="sm" onClick={() => void loadReceipt()}>
                View receipt
              </Button>
            </div>
          ) : receipt ? (
            <dl className="border-separator grid gap-2 rounded-xl border p-4 text-callout sm:grid-cols-2">
              <dt className="text-label-secondary">Receipt</dt>
              <dd className="font-medium">
                {receipt.title}, version {receipt.version}
              </dd>
              <dt className="text-label-secondary">Confirmed by</dt>
              <dd>{receipt.employee_name}</dd>
              <dt className="text-label-secondary">Date and time</dt>
              <dd>{formatUkDateTime(receipt.accepted_at)}</dd>
              <dt className="text-label-secondary">Method</dt>
              <dd>
                {
                  ACCEPTANCE_STATUS[receipt.confirmation_mode === "sign" ? "signed" : "accepted"]
                    .label
                }
              </dd>
              {receipt.typed_signature && (
                <>
                  <dt className="text-label-secondary">Typed signature</dt>
                  <dd className="break-words">{receipt.typed_signature}</dd>
                </>
              )}
              <dt className="text-label-secondary">IP address</dt>
              <dd>{receipt.ip ?? "Not recorded"}</dd>
              <dt className="text-label-secondary">Ref</dt>
              <dd className="break-all font-mono text-footnote">{receipt.id}</dd>
            </dl>
          ) : (
            <p className="text-callout text-label-secondary">Loading receipt…</p>
          )}
          <p className="text-footnote text-label-secondary">
            Receipts are kept as they were recorded and cannot be changed.
          </p>
        </div>
      )}
    </Card>
  );
}
