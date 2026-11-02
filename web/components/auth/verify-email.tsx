"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { TextField } from "@/components/ui/text-field";
import { destinationAfterSignIn } from "@/lib/auth/next-step";
import { attempt, type Problem } from "@/lib/auth/request";

import { Turnstile, TURNSTILE_SITE_KEY } from "./turnstile";

type State = { step: "checking" } | { step: "failed"; problem: Problem | null };

/** The link in the verification e-mail: confirms the address, signs in, and goes to the dashboard. */
export function VerifyEmail({ token }: { token: string | undefined }) {
  const router = useRouter();
  const [state, setState] = useState<State>(
    token ? { step: "checking" } : { step: "failed", problem: null },
  );
  // A token works once. React runs effects twice in development, so only the first run may spend it.
  const spent = useRef(false);

  useEffect(() => {
    if (!token || spent.current) return;
    spent.current = true;
    void attempt((client) => client.POST("/auth/verify-email", { body: { token } })).then(
      (outcome) => {
        if (outcome.ok) router.replace(destinationAfterSignIn(outcome.data));
        else setState({ step: "failed", problem: outcome.problem });
      },
    );
  }, [token, router]);

  if (state.step === "checking") {
    return (
      <div role="status" className="text-body text-label-secondary flex items-center gap-3">
        <Spinner />
        <span>Confirming your email address…</span>
      </div>
    );
  }
  return <Resend problem={state.problem} />;
}

function Resend({ problem }: { problem: Problem | null }) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<Problem | null>(null);
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
      setError({ code: "TURNSTILE_PENDING", message: "Complete the check below, then try again." });
      return;
    }
    setBusy(true);
    setError(null);
    const outcome = await attempt((client) =>
      client.POST("/auth/resend-verification", {
        body: { email: email.trim(), ...(token ? { turnstile_token: token } : {}) },
      }),
    );
    setBusy(false);
    if (outcome.ok) setSent(true);
    else {
      setError(outcome.problem);
      setToken(null);
      setChallenge((count) => count + 1);
    }
  }

  if (sent) {
    return (
      <div className="flex flex-col gap-4">
        <Alert tone="success" title="Check your inbox">
          If that address needs confirming, we have sent a new link. It works once and expires in 24
          hours.
        </Alert>
        <Button asChild variant="gray" size="lg">
          <Link href="/login">Back to sign in</Link>
        </Button>
      </div>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <Alert tone="warning" title="This link cannot be used">
        {problem?.code === "TOKEN_INVALID"
          ? problem.message
          : (problem?.message ?? "This link is not complete.")}{" "}
        Enter your email address and we will send a new one.
      </Alert>
      {error ? <Alert tone="danger" title={error.message} /> : null}
      <TextField
        label="Email address"
        type="email"
        name="email"
        autoComplete="email"
        inputMode="email"
        autoCapitalize="none"
        spellCheck={false}
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        error={fieldError}
      />
      <Turnstile onToken={setToken} resetKey={challenge} />
      <Button type="submit" size="lg" loading={busy}>
        Send a new link
      </Button>
    </form>
  );
}
