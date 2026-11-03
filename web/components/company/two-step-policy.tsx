"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { RadioCards } from "@/components/ui/radio-cards";
import { TextField } from "@/components/ui/text-field";
import { FormSheet } from "./form-sheet";
import { useToast } from "@/components/ui/toast";
import { attempt, type Problem } from "@/lib/auth/request";
import type { components } from "@/lib/api/client";

type Policy = components["schemas"]["TwoStepPolicy"];

const OPTIONS = [
  {
    value: "optional",
    title: "Optional for everyone",
    description: "People can turn on two-step verification in their own settings.",
  },
  {
    value: "admins",
    title: "Required for Company Admins",
    description: "Company Admins must set it up. Everyone else can choose.",
  },
  {
    value: "all",
    title: "Required for all users",
    description: "Everyone must set it up before they can use the company.",
  },
] as const;

/** The company's two-step verification policy (plan 8.15). It saves as soon as one is chosen. */
export function TwoStepPolicyCard({ policy, mayChange }: { policy: Policy; mayChange: boolean }) {
  const router = useRouter();
  const toast = useToast();
  const [choice, setChoice] = useState(policy.policy);
  const [busy, setBusy] = useState(false);

  const [pending, setPending] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);

  async function confirm(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    const confirmed = await attempt((api) => api.POST("/auth/step-up", { body: { password } }));
    setBusy(false);
    setPassword("");
    if (!confirmed.ok) return setProblem(confirmed.problem);
    if (pending) await change(pending);
  }

  async function change(next: string) {
    const previous = choice;
    setChoice(next as Policy["policy"]);
    setBusy(true);
    const outcome = await attempt((api) =>
      api.PUT("/security/two-step", { body: { policy: next as Policy["policy"] } }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: "Two-step policy saved", tone: "success" });
      setPending(null);
      setProblem(null);
      router.refresh();
    } else {
      setChoice(previous);
      if (outcome.problem.code === "STEP_UP_REQUIRED") {
        setPending(next);
        setProblem(outcome.problem);
      } else toast.show({ title: outcome.problem.message, tone: "danger" });
    }
  }

  return (
    <section aria-labelledby="two-step-heading" className="flex flex-col gap-3">
      <h2 id="two-step-heading" className="text-title-3 text-label">
        Two-step verification
      </h2>
      <RadioCards
        legend="Two-step verification policy"
        columns={3}
        value={choice}
        disabled={!mayChange || busy}
        onValueChange={(value) => void change(value)}
        options={OPTIONS}
      />
      {policy.policy !== "optional" && policy.to_set_up > 0 ? (
        <Alert
          tone="info"
          title={`${policy.to_set_up} ${policy.to_set_up === 1 ? "person has" : "people have"} not set it up yet`}
        >
          They are asked to set it up the next time they open a page.
        </Alert>
      ) : null}
      {pending ? (
        <FormSheet
          open
          onOpenChange={(open) => {
            if (!open) {
              setPending(null);
              setPassword("");
            }
          }}
          title="Confirm two-step policy change"
          description="Confirm your password to change who must use two-step verification."
          onSubmit={confirm}
          busy={busy}
          problem={problem}
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
    </section>
  );
}
