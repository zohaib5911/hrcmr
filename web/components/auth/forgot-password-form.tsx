"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import { attempt, type Problem } from "@/lib/auth/request";

import { Turnstile, TURNSTILE_SITE_KEY } from "./turnstile";

/** Asks for a reset link. The answer is the same whether or not the address has an account. */
export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [token, setToken] = useState<string | null>(null);
  const [challenge, setChallenge] = useState(0);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!email.trim()) {
      setFieldError("Enter your email address.");
      return;
    }
    setFieldError(undefined);
    if (TURNSTILE_SITE_KEY && !token) {
      setProblem({
        code: "TURNSTILE_PENDING",
        message: "Complete the check below, then try again.",
      });
      return;
    }
    setBusy(true);
    setProblem(null);
    const outcome = await attempt((client) =>
      client.POST("/auth/forgot-password", {
        body: { email: email.trim(), ...(token ? { turnstile_token: token } : {}) },
      }),
    );
    setBusy(false);
    if (outcome.ok) {
      setSentTo(email.trim());
      return;
    }
    setProblem(outcome.problem);
    setToken(null);
    setChallenge((count) => count + 1);
  }

  if (sentTo) {
    return (
      <div className="flex flex-col gap-4">
        <Alert tone="success" title="Check your inbox">
          If there is an account for {sentTo}, we have sent a link to choose a new password. It
          works once and expires in 1 hour.
        </Alert>
        <Button asChild variant="gray" size="lg">
          <Link href="/login">Back to sign in</Link>
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {problem ? <Alert tone="danger" title={problem.message} /> : null}
      <TextField
        label="Email address"
        type="email"
        name="email"
        autoComplete="email"
        inputMode="email"
        autoCapitalize="none"
        spellCheck={false}
        autoFocus
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        error={fieldError}
      />
      <Turnstile onToken={setToken} resetKey={challenge} />
      <Button type="submit" size="lg" loading={busy}>
        Send reset link
      </Button>
      <Button asChild variant="plain">
        <Link href="/login">Back to sign in</Link>
      </Button>
    </form>
  );
}
