"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import { destinationAfterSignIn, needsTurnstile } from "@/lib/auth/next-step";
import { attempt, type Problem } from "@/lib/auth/request";
import { cn } from "@/lib/utils";

import { PasswordField } from "./password-field";
import { Turnstile, TURNSTILE_SITE_KEY } from "./turnstile";

const REGIONS = [
  { code: "uk", label: "United Kingdom", enabled: true },
  { code: "us", label: "USA", enabled: false },
  { code: "au", label: "Australia", enabled: false },
] as const;

/** UK only for now. The other two are shown so people can see what is coming, and cannot be chosen. */
function RegionSwitch() {
  return (
    <div
      role="group"
      aria-label="Region"
      className="bg-fill-secondary rounded-control flex gap-0.5 p-0.5"
    >
      {REGIONS.map((region) => (
        <button
          key={region.code}
          type="button"
          aria-pressed={region.enabled}
          aria-disabled={!region.enabled}
          onClick={(event) => event.preventDefault()}
          className={cn(
            "text-callout hit-target flex min-w-0 flex-1 flex-col items-center justify-center rounded-[8px] px-2 py-1.5 leading-tight font-medium",
            "focus-visible:outline-accent outline-none focus-visible:outline-2 focus-visible:outline-offset-2",
            region.enabled
              ? "bg-elevated text-label shadow-e1"
              : "text-label-secondary cursor-not-allowed",
          )}
        >
          <span className="truncate">{region.label}</span>
          {region.enabled ? null : <span className="text-caption">Coming soon</span>}
        </button>
      ))}
    </div>
  );
}

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [failures, setFailures] = useState(0);
  const [token, setToken] = useState<string | null>(null);
  const [challenge, setChallenge] = useState(0);
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});

  const showCheck = Boolean(TURNSTILE_SITE_KEY) && needsTurnstile(failures, problem?.code);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const errors = {
      ...(email.trim() ? {} : { email: "Enter your email address." }),
      ...(password ? {} : { password: "Enter your password." }),
    };
    setFieldErrors(errors);
    if (errors.email || errors.password) return;
    if (showCheck && !token) {
      setProblem({
        code: "TURNSTILE_PENDING",
        message: "Complete the check below, then try again.",
      });
      return;
    }
    setBusy(true);
    setProblem(null);
    const outcome = await attempt((client) =>
      client.POST("/auth/login", {
        body: { email: email.trim(), password, ...(token ? { turnstile_token: token } : {}) },
      }),
    );
    if (outcome.ok) {
      router.push(destinationAfterSignIn(outcome.data));
      return;
    }
    setBusy(false);
    setProblem(outcome.problem);
    if (outcome.problem.code === "INVALID_CREDENTIALS") setFailures((count) => count + 1);
    setToken(null);
    setChallenge((count) => count + 1);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <RegionSwitch />
      {problem ? <Alert tone="danger" title={problem.message} /> : null}
      <TextField
        label="Email address"
        type="email"
        name="email"
        autoComplete="username"
        inputMode="email"
        autoCapitalize="none"
        spellCheck={false}
        required
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        error={fieldErrors.email}
      />
      <PasswordField
        label="Password"
        name="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        error={fieldErrors.password}
      />
      {showCheck ? <Turnstile onToken={setToken} resetKey={challenge} /> : null}
      <div className="flex justify-end">
        <Button asChild variant="plain" size="sm">
          <Link href="/forgot-password">Forgot password?</Link>
        </Button>
      </div>
      <Button type="submit" size="lg" loading={busy}>
        Sign in
      </Button>
      <p className="text-callout text-label-secondary text-center">
        New here?{" "}
        <Link
          href="/setup"
          className="text-accent-text font-semibold underline-offset-4 hover:underline"
        >
          Create your company account
        </Link>
      </p>
    </form>
  );
}
