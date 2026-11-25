"use client";

import { Dialog } from "radix-ui";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { attempt, type Problem } from "@/lib/auth/request";
import { signOut } from "@/lib/auth/sign-out";

/**
 * Shown over everything when there are terms the person has not accepted (plan 8.1): nothing behind
 * it can be reached, and Esc does not close it. They accept, or they sign out.
 */
export function TermsGate({ version }: { version: string }) {
  const router = useRouter();
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [missing, setMissing] = useState(false);

  async function accept() {
    if (!accepted) {
      setMissing(true);
      return;
    }
    setMissing(false);
    setBusy(true);
    setProblem(null);
    const outcome = await attempt((client) =>
      client.POST("/auth/accept-terms", { body: { version } }),
    );
    if (outcome.ok) {
      router.refresh();
      return;
    }
    setBusy(false);
    setProblem(outcome.problem);
  }

  async function leave() {
    setProblem(null);
    const outcome = await signOut();
    if (!outcome.ok) {
      setProblem(outcome.problem);
      return;
    }
    router.push("/login");
    router.refresh();
  }

  return (
    <Dialog.Root open modal>
      <Dialog.Portal>
        <Dialog.Content
          onEscapeKeyDown={(event) => event.preventDefault()}
          onPointerDownOutside={(event) => event.preventDefault()}
          onInteractOutside={(event) => event.preventDefault()}
          aria-describedby="terms-gate-description"
          className="bg-grouped fixed inset-0 z-[80] flex items-center justify-center overflow-y-auto p-4 outline-none sm:p-8"
        >
          <div className="bg-elevated rounded-card shadow-e3 flex w-full max-w-md flex-col gap-5 p-6 sm:p-8">
            <div className="flex flex-col gap-2">
              <Dialog.Title className="text-title-2 text-label text-balance">
                Please accept our terms
              </Dialog.Title>
              <Dialog.Description
                id="terms-gate-description"
                className="text-body text-label-secondary text-pretty"
              >
                Our terms of service have changed. Read them, then accept to carry on with your
                work.
              </Dialog.Description>
            </div>
            <p className="text-callout">
              <a
                href="/legal/terms"
                target="_blank"
                rel="noreferrer"
                className="text-accent-text underline-offset-4 hover:underline"
              >
                Terms of service
              </a>
              {" · "}
              <a
                href="/legal/privacy"
                target="_blank"
                rel="noreferrer"
                className="text-accent-text underline-offset-4 hover:underline"
              >
                Privacy notice
              </a>
            </p>
            {problem ? <Alert tone="danger" title={problem.message} /> : null}
            <div className="flex flex-col gap-1">
              <Checkbox
                checked={accepted}
                onCheckedChange={(value) => setAccepted(value === true)}
                label="I accept the terms of service"
                aria-invalid={missing && !accepted ? true : undefined}
              />
              {missing && !accepted ? (
                <p role="alert" className="text-footnote text-danger pl-8">
                  Accept the terms to continue.
                </p>
              ) : null}
            </div>
            <Button size="lg" loading={busy} onClick={() => void accept()}>
              Continue
            </Button>
            <Button variant="plain" onClick={() => void leave()}>
              Sign out
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
