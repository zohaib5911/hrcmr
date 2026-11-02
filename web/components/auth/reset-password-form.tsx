"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { MIN_PASSWORD_LENGTH } from "@/lib/auth/password";
import { attempt, type Problem } from "@/lib/auth/request";

import { PasswordField } from "./password-field";

/** Choosing a new password from the link in the e-mail. */
export function ResetPasswordForm({ token }: { token: string | undefined }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [done, setDone] = useState(false);
  const [fieldError, setFieldError] = useState<string | undefined>();

  if (!token) {
    return <NewLink message="This link is not complete. Ask for a new one." />;
  }
  if (done) {
    return (
      <div className="flex flex-col gap-4">
        <Alert tone="success" title="Your password has been changed">
          You have been signed out everywhere else. Sign in with your new password.
        </Alert>
        <Button asChild size="lg">
          <Link href="/login">Sign in</Link>
        </Button>
      </div>
    );
  }
  const linkProblem = problem && problem.code === "TOKEN_INVALID";
  if (linkProblem) return <NewLink message={problem.message} />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if ([...password].length < MIN_PASSWORD_LENGTH) {
      setFieldError(`Use at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    setFieldError(undefined);
    setBusy(true);
    setProblem(null);
    const outcome = await attempt((client) =>
      client.POST("/auth/reset-password", { body: { token: token ?? "", new_password: password } }),
    );
    setBusy(false);
    if (outcome.ok) {
      setDone(true);
      return;
    }
    if (outcome.problem.field === "new_password") setFieldError(outcome.problem.message);
    else setProblem(outcome.problem);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {problem ? <Alert tone="danger" title={problem.message} /> : null}
      <PasswordField
        label="New password"
        name="new_password"
        autoComplete="new-password"
        autoFocus
        meter
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        error={fieldError}
      />
      <Button type="submit" size="lg" loading={busy}>
        Change password
      </Button>
    </form>
  );
}

function NewLink({ message }: { message: string }) {
  return (
    <div className="flex flex-col gap-4">
      <Alert tone="warning" title="This link cannot be used">
        {message}
      </Alert>
      <Button asChild size="lg">
        <Link href="/forgot-password">Send me a new link</Link>
      </Button>
    </div>
  );
}
