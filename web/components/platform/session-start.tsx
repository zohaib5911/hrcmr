"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import { createApiClient } from "@/lib/api/client";
import { baseUrl, ensureCsrfCookie } from "@/lib/auth/request";
import { safeNextPath } from "@/lib/platform/session";

export type StartResult = { ok: true } | { ok: false; code: string };

/**
 * Starts the platform session from the browser (C3.1.2). The API's Set-Cookie then lands on this
 * admin host, and the API sees the admin's own address and user agent (the network rule and the
 * audit row). It uses its own client, without the shared enrolment redirect: a refusal must reach
 * the refusal page, not the set-up screen, which does not exist on the admin host.
 */
export async function startFromBrowser(): Promise<StartResult> {
  try {
    await ensureCsrfCookie();
    const client = createApiClient({ baseUrl: baseUrl() });
    const { response, error } = await client.POST("/auth/platform-session");
    if (response.ok) return { ok: true };
    return { ok: false, code: errorCode(error) };
  } catch {
    return { ok: false, code: "UNREACHABLE" };
  }
}

/**
 * Confirms it is the admin again (POST /auth/step-up with an authenticator or recovery code). The
 * platform session needs one from the last 10 minutes, so a stolen tenant session cannot open the
 * admin site by itself (O6.1.7).
 */
export async function stepUpFromBrowser(code: string): Promise<StartResult> {
  try {
    await ensureCsrfCookie();
    const client = createApiClient({ baseUrl: baseUrl() });
    const { response, error } = await client.POST("/auth/step-up", { body: { code } });
    if (response.ok) return { ok: true };
    return { ok: false, code: errorCode(error) };
  } catch {
    return { ok: false, code: "UNREACHABLE" };
  }
}

function errorCode(error: unknown): string {
  const code = (error as { error?: { code?: unknown } } | undefined)?.error?.code;
  return typeof code === "string" ? code : "UNKNOWN";
}

function goTo(path: string): void {
  window.location.replace(path);
}

/**
 * Starts the platform session, then goes on to `next` (checked again here), or to the refusal page
 * with the reason. When the API asks for a fresh step-up, the admin enters a code here first. The
 * ref makes sure only one start is sent, even under React's strict mode.
 */
export function SessionStart({
  next,
  run = startFromBrowser,
  stepUp = stepUpFromBrowser,
  navigate = goTo,
}: {
  next: string;
  run?: () => Promise<StartResult>;
  stepUp?: (code: string) => Promise<StartResult>;
  navigate?: (path: string) => void;
}) {
  const started = useRef(false);
  const [confirming, setConfirming] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void run().then((result) => {
      if (result.ok) navigate(safeNextPath(next));
      else if (result.code === "STEP_UP_REQUIRED") setConfirming(true);
      else navigate(`/session-required?code=${encodeURIComponent(result.code)}`);
    });
  }, [next, run, navigate]);

  async function confirm(event: FormEvent) {
    event.preventDefault();
    const entered = code.replace(/\s+/g, "");
    if (!entered) return;
    setBusy(true);
    setRefused(false);
    const confirmed = await stepUp(entered);
    if (!confirmed.ok) {
      setBusy(false);
      setCode("");
      if (confirmed.code === "UNAUTHENTICATED") {
        navigate("/session-required?code=UNAUTHENTICATED");
      } else setRefused(true);
      return;
    }
    const result = await run();
    if (result.ok) navigate(safeNextPath(next));
    else navigate(`/session-required?code=${encodeURIComponent(result.code)}`);
  }

  if (confirming) {
    return (
      <form onSubmit={confirm} noValidate className="mt-4 flex flex-col gap-4">
        <p className="text-body">
          Confirm it is you to open the admin site. Enter the code from your authenticator app.
        </p>
        {refused ? <Alert tone="danger" title="That code did not work. Try again." /> : null}
        <TextField
          label="Code"
          name="code"
          autoComplete="one-time-code"
          autoCapitalize="none"
          spellCheck={false}
          autoFocus
          value={code}
          onChange={(event) => setCode(event.target.value)}
          hint="The 6 digits from your app, or one of your recovery codes."
        />
        <Button type="submit" size="lg" loading={busy}>
          Continue
        </Button>
      </form>
    );
  }

  return (
    <p role="status" className="mt-4 text-body">
      Starting a platform session…
    </p>
  );
}
