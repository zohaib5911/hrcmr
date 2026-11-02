"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import { attempt, type Problem } from "@/lib/auth/request";

type Mode = "app" | "recovery";

/** The second step of signing in: the 6-digit code from the authenticator app, or a recovery code. */
export function MfaForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("app");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [fieldError, setFieldError] = useState<string | undefined>();

  function switchMode() {
    setMode((current) => (current === "app" ? "recovery" : "app"));
    setCode("");
    setProblem(null);
    setFieldError(undefined);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const entered = code.replace(/\s+/g, "");
    if (mode === "app" ? !/^\d{6}$/.test(entered) : entered.length < 8) {
      setFieldError(
        mode === "app" ? "Enter the 6 digits from your app." : "Enter one of your recovery codes.",
      );
      return;
    }
    setFieldError(undefined);
    setBusy(true);
    setProblem(null);
    const outcome = await attempt((client) =>
      client.POST("/auth/mfa/challenge", { body: { code: entered } }),
    );
    if (outcome.ok) {
      router.push("/dashboard");
      return;
    }
    setBusy(false);
    setProblem(outcome.problem);
    setCode("");
  }

  const expired = problem?.code === "UNAUTHENTICATED" || problem?.code === "HTTP_401";

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {problem ? (
        <Alert
          tone="danger"
          title={expired ? "Your sign-in has timed out." : problem.message}
          {...(expired
            ? {
                action: (
                  <Button asChild variant="gray" size="sm">
                    <Link href="/login">Start again</Link>
                  </Button>
                ),
              }
            : {})}
        />
      ) : null}
      {mode === "app" ? (
        <TextField
          key="app"
          label="6-digit code"
          name="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={7}
          autoFocus
          value={code}
          onChange={(event) => setCode(event.target.value)}
          error={fieldError}
          hint="Open your authenticator app and enter the code it shows."
        />
      ) : (
        <TextField
          key="recovery"
          label="Recovery code"
          name="recovery_code"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          autoFocus
          value={code}
          onChange={(event) => setCode(event.target.value)}
          error={fieldError}
          hint="Each recovery code works once."
        />
      )}
      <Button type="submit" size="lg" loading={busy}>
        Verify
      </Button>
      <Button variant="plain" onClick={switchMode}>
        {mode === "app" ? "Use a recovery code" : "Use your authenticator app"}
      </Button>
    </form>
  );
}
