"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioCards } from "@/components/ui/radio-cards";
import { Stepper } from "@/components/ui/stepper";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { MIN_PASSWORD_LENGTH } from "@/lib/auth/password";
import { attempt, type Problem } from "@/lib/auth/request";

import { AuthCard } from "./auth-card";
import { PasswordField } from "./password-field";
import { Turnstile, TURNSTILE_SITE_KEY } from "./turnstile";

type Region = components["schemas"]["SignupRequest"]["bank_holiday_region"] & string;

const REGIONS: readonly { value: Region; title: string; description: string }[] = [
  {
    value: "england-and-wales",
    title: "England and Wales",
    description: "Uses the bank holidays for England and Wales.",
  },
  { value: "scotland", title: "Scotland", description: "Uses the bank holidays for Scotland." },
  {
    value: "northern-ireland",
    title: "Northern Ireland",
    description: "Uses the bank holidays for Northern Ireland.",
  },
];
const STEPS = [
  { id: "company", label: "Company" },
  { id: "account", label: "Your account" },
] as const;
const RESEND_WAIT_SECONDS = 60;

type Errors = Partial<
  Record<"company_name" | "first_name" | "last_name" | "email" | "password" | "terms", string>
>;

/** Counts down once a second from `seconds`; `restart` begins again. */
function useCountdown(seconds: number) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    if (left <= 0) return;
    const timer = window.setTimeout(() => setLeft((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [left]);
  return { left, restart: () => setLeft(seconds) };
}

/** Creating a company and its first administrator, in two steps, then waiting for the e-mail link. */
export function SetupWizard() {
  const [step, setStep] = useState<0 | 1>(0);
  const [companyName, setCompanyName] = useState("");
  const [region, setRegion] = useState<Region>("england-and-wales");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [terms, setTerms] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [challenge, setChallenge] = useState(0);
  const [sentTo, setSentTo] = useState<string | null>(null);

  function next(event: FormEvent) {
    event.preventDefault();
    if (!companyName.trim()) {
      setErrors({ company_name: "Enter your company name." });
      return;
    }
    setErrors({});
    setStep(1);
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    const found: Errors = {
      ...(firstName.trim() ? {} : { first_name: "Enter your first name." }),
      ...(lastName.trim() ? {} : { last_name: "Enter your last name." }),
      ...(/^\S+@\S+\.\S+$/.test(email.trim())
        ? {}
        : { email: "Enter a valid work email address." }),
      ...([...password].length >= MIN_PASSWORD_LENGTH
        ? {}
        : { password: `Use at least ${MIN_PASSWORD_LENGTH} characters.` }),
      ...(terms ? {} : { terms: "Accept the terms to create your account." }),
    };
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0) return;
    if (TURNSTILE_SITE_KEY && !token) {
      setProblem({
        code: "TURNSTILE_PENDING",
        message: "Complete the check below, then try again.",
      });
      return;
    }
    setBusy(true);
    const outcome = await attempt((client) =>
      client.POST("/auth/signup", {
        body: {
          company_name: companyName.trim(),
          bank_holiday_region: region,
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          email: email.trim(),
          password,
          accept_terms: terms,
          ...(token ? { turnstile_token: token } : {}),
        },
      }),
    );
    setBusy(false);
    if (outcome.ok) {
      setSentTo(email.trim());
      return;
    }
    const { field, message } = outcome.problem;
    setToken(null);
    setChallenge((count) => count + 1);
    if (field === "company_name" || field === "bank_holiday_region") {
      setErrors({ company_name: message });
      setStep(0);
    } else if (field === "first_name" || field === "last_name" || field === "email") {
      setErrors({ [field]: message });
    } else if (field === "password") {
      setErrors({ password: message });
    } else if (field === "accept_terms") {
      setErrors({ terms: message });
    } else {
      setProblem(outcome.problem);
    }
  }

  if (sentTo) {
    return (
      <AuthCard
        title="Check your inbox"
        description={
          <>
            We have sent a link to{" "}
            <strong className="text-label font-semibold break-words">{sentTo}</strong>. Open it to
            confirm your email address and start using your account.
          </>
        }
      >
        <CheckInbox email={sentTo} onWrongAddress={() => setSentTo(null)} />
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create your company account"
      description="Free to start, with no card needed. It takes two short steps."
    >
      <Stepper steps={STEPS} current={step} />
      {step === 0 ? (
        <form onSubmit={next} noValidate className="flex flex-col gap-4">
          <TextField
            label="Company name"
            name="company_name"
            autoComplete="organization"
            maxLength={200}
            autoFocus
            value={companyName}
            onChange={(event) => setCompanyName(event.target.value)}
            error={errors.company_name}
          />
          <RadioCards
            legend="Where is your company based?"
            options={REGIONS}
            value={region}
            onValueChange={(value) => setRegion(value as Region)}
          />
          <p className="text-footnote text-label-secondary -mt-1">
            This decides which bank holidays your team gets. You can change it later.
          </p>
          <Button type="submit" size="lg">
            Continue
          </Button>
          <p className="text-callout text-label-secondary text-center">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-accent-text font-semibold underline-offset-4 hover:underline"
            >
              Sign in
            </Link>
          </p>
        </form>
      ) : (
        <form onSubmit={create} noValidate className="flex flex-col gap-4">
          <details className="bg-fill-secondary rounded-control text-callout group px-4 py-3">
            <summary className="text-label cursor-pointer font-medium">Your choices so far</summary>
            <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
              <dt className="text-label">Company</dt>
              <dd className="text-label min-w-0 font-medium break-words">{companyName.trim()}</dd>
              <dt className="text-label">Based in</dt>
              <dd className="text-label font-medium">
                {REGIONS.find((item) => item.value === region)?.title}
              </dd>
            </dl>
          </details>
          {problem ? <Alert tone="danger" title={problem.message} /> : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="First name"
              name="first_name"
              autoComplete="given-name"
              autoFocus
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
          <TextField
            label="Work email"
            type="email"
            name="email"
            autoComplete="email"
            inputMode="email"
            autoCapitalize="none"
            spellCheck={false}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            error={errors.email}
          />
          <PasswordField
            label="Password"
            name="password"
            autoComplete="new-password"
            meter
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={errors.password}
          />
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
          <Turnstile onToken={setToken} resetKey={challenge} />
          <Button type="submit" size="lg" loading={busy}>
            Create account
          </Button>
          <Button variant="plain" onClick={() => setStep(0)}>
            Back
          </Button>
        </form>
      )}
    </AuthCard>
  );
}

function CheckInbox({ email, onWrongAddress }: { email: string; onWrongAddress: () => void }) {
  const { left, restart } = useCountdown(RESEND_WAIT_SECONDS);
  const [busy, setBusy] = useState(false);
  const [resent, setResent] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [challenge, setChallenge] = useState(0);

  async function resend() {
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
      client.POST("/auth/resend-verification", {
        body: { email, ...(token ? { turnstile_token: token } : {}) },
      }),
    );
    setBusy(false);
    setToken(null);
    setChallenge((count) => count + 1);
    if (outcome.ok) {
      setResent(true);
      restart();
    } else {
      setProblem(outcome.problem);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {resent ? (
        <Alert tone="success" title="We have sent it again">
          It can take a minute to arrive. Check your junk folder too.
        </Alert>
      ) : null}
      {problem ? <Alert tone="danger" title={problem.message} /> : null}
      <Turnstile onToken={setToken} resetKey={challenge} />
      <Button
        variant="gray"
        size="lg"
        loading={busy}
        aria-disabled={left > 0 || undefined}
        onClick={() => {
          if (left === 0) void resend();
        }}
      >
        Send the email again
      </Button>
      <p className="text-footnote text-label-secondary text-center" aria-live="polite">
        {left > 0
          ? `You can ask for another one in ${left} ${left === 1 ? "second" : "seconds"}.`
          : "Not there yet? You can ask for another one."}
      </p>
      <Button variant="plain" onClick={onWrongAddress}>
        Wrong address? Start again
      </Button>
    </div>
  );
}
