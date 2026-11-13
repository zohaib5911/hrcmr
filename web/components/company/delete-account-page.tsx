"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { attempt, type Problem } from "@/lib/auth/request";
import type { components } from "@/lib/api/client";

import { FormSheet } from "./form-sheet";

type Deletion = components["schemas"]["DeletionOut"];

const LONDON_DATE = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Europe/London",
});

function onDay(instant: string | null | undefined): string {
  return instant ? LONDON_DATE.format(new Date(instant)) : "";
}

const DELETED = [
  "Every employee record, with their documents, right to work checks and history",
  "Leave, rotas, time and attendance, policies, training and recruitment",
  "Sponsor compliance records, reports and saved checks",
  "Every user account that belongs only to this company",
];

/**
 * Plan 8.16. Ask, enter the 6-digit code from the e-mail, and the deletion is scheduled 7 days on.
 * Any Company Admin can withdraw it until then.
 */
export function DeleteAccountPage({
  allowed,
  request = null,
  companyName = "",
}: {
  allowed: boolean;
  request?: Deletion | null;
  companyName?: string;
}) {
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [withExport, setWithExport] = useState(false);
  const [code, setCode] = useState("");
  const [codeProblem, setCodeProblem] = useState<string | undefined>();
  const [stepUp, setStepUp] = useState(false);
  const [password, setPassword] = useState("");
  const [stepUpProblem, setStepUpProblem] = useState<Problem | null>(null);

  if (!allowed) {
    return (
      <>
        <PageHeader title="Delete company account" />
        <Alert tone="info" title="Only Company Admins can do this">
          Ask a Company Admin if the company account should be deleted.
        </Alert>
      </>
    );
  }

  async function start(): Promise<void> {
    setBusy(true);
    const outcome = await attempt((api) =>
      api.POST("/companies/me/deletion-request", { body: { export_requested: withExport } }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: "We have e-mailed you a code", tone: "success" });
      router.refresh();
      return;
    }
    if (outcome.problem.code === "STEP_UP_REQUIRED") {
      setStepUp(true);
      return;
    }
    toast.show({ title: outcome.problem.message, tone: "danger" });
  }

  async function confirmPassword(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    const confirmed = await attempt((api) => api.POST("/auth/step-up", { body: { password } }));
    setBusy(false);
    setPassword("");
    if (!confirmed.ok) return setStepUpProblem(confirmed.problem);
    setStepUp(false);
    setStepUpProblem(null);
    await start();
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    const outcome = await attempt((api) =>
      api.POST("/companies/me/deletion-request/confirm", { body: { code } }),
    );
    setBusy(false);
    if (outcome.ok) {
      setCode("");
      toast.show({
        title: `The account will be deleted on ${onDay(outcome.data.scheduled_for)}`,
        tone: "success",
      });
      router.refresh();
      return;
    }
    setCodeProblem(outcome.problem.message);
  }

  async function withdraw(): Promise<void> {
    const outcome = await attempt((api) => api.DELETE("/companies/me/deletion-request"));
    if (!outcome.ok) {
      toast.show({ title: outcome.problem.message, tone: "danger" });
      return;
    }
    toast.show({ title: "The deletion request was withdrawn", tone: "success" });
    router.refresh();
  }

  const withdrawButton = (label: string) => (
    <ConfirmDialog
      trigger={<Button variant="gray">{label}</Button>}
      title="Withdraw the deletion request?"
      description="Nothing will be deleted and the account stays open."
      confirmLabel="Withdraw request"
      onConfirm={withdraw}
    />
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Delete company account"
        description="Delete the company and everything in it. This cannot be undone."
      />

      {request?.status === "scheduled" ? (
        <Alert
          tone="danger"
          title={`This account will be deleted on ${onDay(request.scheduled_for)}`}
        >
          {request.requested_by_name ?? "A Company Admin"} confirmed the request. Any Company Admin
          can withdraw it until then.
        </Alert>
      ) : null}
      {request?.status === "awaiting_code" && !request.requested_by_me ? (
        <Alert tone="warning" title="A deletion request has been started">
          {request.requested_by_name ?? "Another Company Admin"} asked to delete the account and has
          not entered the code yet.
        </Alert>
      ) : null}

      <Card>
        <CardHeader title="What is deleted" headingLevel={2} />
        <CardBody className="flex flex-col gap-3">
          <ul className="text-label-secondary list-disc pl-5">
            {DELETED.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="text-label-secondary">
            We keep only what the law requires: payment and invoice records, and a note of the date
            the account was deleted.
          </p>
        </CardBody>
      </Card>

      {request === null ? (
        <Card>
          <CardHeader
            title="Delete the account"
            headingLevel={2}
            description="We e-mail you a 6-digit code. Once you enter it, the account is deleted 7 days later."
          />
          <CardBody className="flex flex-col gap-4">
            <Checkbox
              label="Send me a full data export first"
              description="A zip of all records and documents, linked by e-mail for 7 days."
              checked={withExport}
              onCheckedChange={(value) => setWithExport(value === true)}
            />
            <div>
              <ConfirmDialog
                trigger={
                  <Button variant="gray" disabled={busy}>
                    Delete company account
                  </Button>
                }
                title="Delete the company account?"
                description="We will e-mail you a code to confirm. Everything is deleted 7 days after you enter it."
                confirmLabel="Send the code"
                destructive
                requireText={companyName || undefined}
                onConfirm={start}
              />
            </div>
          </CardBody>
        </Card>
      ) : null}

      {request?.status === "awaiting_code" && request.requested_by_me ? (
        <Card>
          <CardHeader
            title="Enter the code"
            headingLevel={2}
            description={`We e-mailed you a 6-digit code. It works until ${request.code_expires_at ? new Date(request.code_expires_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" }) : "it expires"}.`}
          />
          <CardBody>
            <form className="flex flex-col gap-4" onSubmit={(event) => void confirm(event)}>
              <TextField
                label="Code"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                error={codeProblem}
                onChange={(event) => {
                  setCode(event.target.value);
                  setCodeProblem(undefined);
                }}
                required
              />
              <div className="flex flex-wrap gap-3">
                <Button type="submit" variant="filled" disabled={busy || code.trim().length < 6}>
                  Confirm deletion
                </Button>
                <Button type="button" variant="gray" disabled={busy} onClick={() => void start()}>
                  Send a new code
                </Button>
                {withdrawButton("Cancel request")}
              </div>
            </form>
          </CardBody>
        </Card>
      ) : null}

      {request !== null && !(request.status === "awaiting_code" && request.requested_by_me) ? (
        <div>{withdrawButton("Withdraw deletion request")}</div>
      ) : null}

      {stepUp ? (
        <FormSheet
          open
          onOpenChange={(open) => {
            if (!open) {
              setStepUp(false);
              setPassword("");
            }
          }}
          title="Confirm it is you"
          description="Confirm your password to start deleting the company account."
          onSubmit={(event) => void confirmPassword(event)}
          busy={busy}
          problem={stepUpProblem}
          saveLabel="Continue"
        >
          <TextField
            label="Your password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </FormSheet>
      ) : null}
    </div>
  );
}
