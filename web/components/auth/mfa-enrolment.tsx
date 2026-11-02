"use client";

import { Copy, Download } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { brand } from "@brand";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { Stepper } from "@/components/ui/stepper";
import { TextField } from "@/components/ui/text-field";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatRecoveryCodes, groupKey } from "@/lib/auth/mfa";

const STEPS = [
  { id: "scan", label: "Scan" },
  { id: "confirm", label: "Confirm" },
  { id: "codes", label: "Recovery codes" },
] as const;

type Setup = { secret: string; qr: string };

interface MfaEnrolmentProps {
  /** Called when the person says they have saved their recovery codes. */
  onDone: () => void;
  /** Offered where the person cannot skip the set-up (a company policy), so they can leave. */
  onSignOut?: () => void;
}

/** Setting up an authenticator app: scan the code, confirm with one 6-digit code, keep the 10 recovery codes. */
export function MfaEnrolment({ onDone, onSignOut }: MfaEnrolmentProps) {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [code, setCode] = useState("");
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [copied, setCopied] = useState(false);
  // Starting set-up replaces any earlier unfinished one, so it must happen once, not on every effect run.
  const started = useRef(false);

  async function start() {
    setProblem(null);
    const outcome = await attempt((client) => client.POST("/auth/mfa/setup"));
    if (!outcome.ok) {
      setProblem(outcome.problem);
      return;
    }
    const qr = await QRCode.toDataURL(outcome.data.otpauth_uri, {
      width: 208,
      // The image carries its own white ground and quiet zone, which scanners need in dark mode too.
      margin: 4,
      errorCorrectionLevel: "M",
    });
    setSetup({ secret: outcome.data.secret, qr });
  }

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void start();
  }, []);

  async function confirm(event: FormEvent) {
    event.preventDefault();
    const entered = code.replace(/\s+/g, "");
    if (!/^\d{6}$/.test(entered)) {
      setFieldError("Enter the 6 digits shown in your app.");
      return;
    }
    setFieldError(undefined);
    setBusy(true);
    const outcome = await attempt((client) =>
      client.POST("/auth/mfa/verify", { body: { code: entered } }),
    );
    setBusy(false);
    if (outcome.ok) {
      setCodes(outcome.data.recovery_codes);
      return;
    }
    if (outcome.problem.code === "MFA_SETUP_EXPIRED") {
      setSetup(null);
      setCode("");
      await start();
      setProblem({
        ...outcome.problem,
        message: "That set-up timed out, so here is a new code to scan.",
      });
      return;
    }
    setFieldError(outcome.problem.message);
    setCode("");
  }

  function download() {
    const file = new Blob([formatRecoveryCodes(brand.name, codes ?? [], new Date())], {
      type: "text/plain",
    });
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = "recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copyKey() {
    if (!setup) return;
    try {
      await navigator.clipboard.writeText(setup.secret);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  if (codes) {
    return (
      <div className="flex flex-col gap-4">
        <Stepper steps={STEPS} current={2} />
        <Alert tone="warning" title="Save these recovery codes now">
          Each one works once, if you ever lose your phone. We show them only this one time.
        </Alert>
        <ul
          aria-label="Recovery codes"
          className="bg-fill-secondary rounded-control text-callout text-label grid grid-cols-2 gap-x-4 gap-y-2 p-4 font-mono tabular-nums"
        >
          {codes.map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
        <Button variant="gray" size="lg" onClick={download}>
          <Icon icon={Download} size={20} />
          Download
        </Button>
        <Button size="lg" onClick={onDone}>
          I&apos;ve saved them
        </Button>
      </div>
    );
  }

  if (!setup) {
    return problem ? (
      <div className="flex flex-col gap-4">
        <Alert tone="danger" title={problem.message} />
        <Button size="lg" onClick={() => void start()}>
          Try again
        </Button>
        {onSignOut ? (
          <Button variant="plain" onClick={onSignOut}>
            Sign out
          </Button>
        ) : null}
      </div>
    ) : (
      <div role="status" className="text-body text-label-secondary flex items-center gap-3">
        <Spinner />
        <span>Getting your code ready…</span>
      </div>
    );
  }

  return (
    <form onSubmit={confirm} noValidate className="flex flex-col gap-4">
      <Stepper steps={STEPS} current={fieldError || code ? 1 : 0} />
      {problem ? <Alert tone="info" title={problem.message} /> : null}
      <p className="text-callout text-label-secondary">
        Open an authenticator app such as Google Authenticator, Microsoft Authenticator or
        1Password, and scan this code.
      </p>
      <div className="flex justify-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={setup.qr}
          alt="QR code for your authenticator app"
          width={208}
          height={208}
          className="rounded-control"
        />
      </div>
      <div className="bg-fill-secondary rounded-control flex items-center justify-between gap-3 p-3">
        <div className="min-w-0">
          <p className="text-footnote text-label">Cannot scan it? Type this key into the app.</p>
          <p className="text-callout text-label font-mono break-all select-all">
            {groupKey(setup.secret)}
          </p>
        </div>
        <Button variant="gray" size="sm" onClick={() => void copyKey()}>
          <Icon icon={Copy} size={16} />
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <TextField
        label="6-digit code"
        name="code"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={7}
        value={code}
        onChange={(event) => setCode(event.target.value)}
        error={fieldError}
        hint="Enter the code your app shows for this account."
      />
      <Button type="submit" size="lg" loading={busy}>
        Confirm
      </Button>
      {onSignOut ? (
        <Button variant="plain" onClick={onSignOut}>
          Sign out
        </Button>
      ) : null}
    </form>
  );
}
