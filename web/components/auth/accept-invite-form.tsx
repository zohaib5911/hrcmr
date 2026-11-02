"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Spinner } from "@/components/ui/spinner";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { destinationAfterSignIn } from "@/lib/auth/next-step";
import { MIN_PASSWORD_LENGTH } from "@/lib/auth/password";
import { attempt, type Problem } from "@/lib/auth/request";
import { ROLE_LABELS } from "@/lib/auth/roles";

import { PasswordField } from "./password-field";

type Invitation = components["schemas"]["InvitationDetails"];
type Load = { step: "loading" } | { step: "ready"; invitation: Invitation } | { step: "invalid" };
type Errors = Partial<Record<"first_name" | "last_name" | "password" | "terms", string>>;

/** Joining a company from an invitation e-mail: name, password, terms. */
export function AcceptInviteForm({ token }: { token: string | undefined }) {
  const [load, setLoad] = useState<Load>(token ? { step: "loading" } : { step: "invalid" });

  useEffect(() => {
    if (!token) return;
    let current = true;
    void attempt((client) =>
      client.GET("/auth/invitations/{token}", { params: { path: { token } } }),
    ).then((outcome) => {
      if (current) {
        setLoad(outcome.ok ? { step: "ready", invitation: outcome.data } : { step: "invalid" });
      }
    });
    return () => {
      current = false;
    };
  }, [token]);

  if (load.step === "loading") {
    return (
      <div role="status" className="text-body text-label-secondary flex items-center gap-3">
        <Spinner />
        <span>Checking your invitation…</span>
      </div>
    );
  }
  if (load.step === "invalid" || !token) {
    return (
      <div className="flex flex-col gap-4">
        <Alert tone="warning" title="This invitation cannot be used">
          It may have expired or already been used. Ask the person who invited you to send another.
        </Alert>
        <Button asChild variant="gray" size="lg">
          <Link href="/login">Back to sign in</Link>
        </Button>
      </div>
    );
  }
  return <InviteFields token={token} invitation={load.invitation} />;
}

function InviteFields({ token, invitation }: { token: string; invitation: Invitation }) {
  const router = useRouter();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [terms, setTerms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [errors, setErrors] = useState<Errors>({});

  async function submit(event: FormEvent) {
    event.preventDefault();
    const found: Errors = {
      ...(firstName.trim() ? {} : { first_name: "Enter your first name." }),
      ...(lastName.trim() ? {} : { last_name: "Enter your last name." }),
      ...(invitation.has_account || [...password].length >= MIN_PASSWORD_LENGTH
        ? {}
        : { password: `Use at least ${MIN_PASSWORD_LENGTH} characters.` }),
      ...(terms ? {} : { terms: "Accept the terms to continue." }),
    };
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    setProblem(null);
    const outcome = await attempt((client) =>
      client.POST("/auth/invitations/{token}/accept", {
        params: { path: { token } },
        body: {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          accept_terms: terms,
          ...(invitation.has_account ? {} : { password }),
        },
      }),
    );
    if (outcome.ok) {
      // Someone who already has an account signs in as usual: an invitation never signs them in.
      router.push(outcome.data.me ? destinationAfterSignIn(outcome.data) : "/login");
      return;
    }
    setBusy(false);
    const { field } = outcome.problem;
    if (field === "password") setErrors({ password: outcome.problem.message });
    else setProblem(outcome.problem);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <dl className="border-separator rounded-control text-callout border grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 p-4">
        <dt className="text-label-secondary">Company</dt>
        <dd className="text-label min-w-0 font-medium break-words">{invitation.company_name}</dd>
        <dt className="text-label-secondary">Your role</dt>
        <dd className="text-label font-medium">{ROLE_LABELS[invitation.role]}</dd>
        <dt className="text-label-secondary">Email</dt>
        <dd className="text-label min-w-0 font-medium break-words">{invitation.email}</dd>
      </dl>
      {invitation.has_account ? (
        <Alert tone="info" title="You already have an account">
          Confirm your name and accept the terms. You will then sign in as usual with your existing
          password.
        </Alert>
      ) : null}
      {problem ? <Alert tone="danger" title={problem.message} /> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="First name"
          name="first_name"
          autoComplete="given-name"
          value={firstName}
          onChange={(event) => setFirstName(event.target.value)}
          error={errors.first_name}
        />
        <TextField
          label="Last name"
          name="last_name"
          autoComplete="family-name"
          value={lastName}
          onChange={(event) => setLastName(event.target.value)}
          error={errors.last_name}
        />
      </div>
      {invitation.has_account ? null : (
        <PasswordField
          label="Choose a password"
          name="password"
          autoComplete="new-password"
          meter
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={errors.password}
        />
      )}
      <div className="flex flex-col gap-1">
        <Checkbox
          checked={terms}
          onCheckedChange={(value) => setTerms(value === true)}
          label="I accept the terms of service and have read the privacy notice"
          aria-invalid={errors.terms ? true : undefined}
        />
        {errors.terms ? (
          <p role="alert" className="text-footnote text-danger pl-8">
            {errors.terms}
          </p>
        ) : null}
        <p className="text-footnote text-label-secondary pl-8">
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
      </div>
      <Button type="submit" size="lg" loading={busy}>
        Join {invitation.company_name}
      </Button>
    </form>
  );
}
