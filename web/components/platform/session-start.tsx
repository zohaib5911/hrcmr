"use client";

import { useEffect, useRef } from "react";

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

function errorCode(error: unknown): string {
  const code = (error as { error?: { code?: unknown } } | undefined)?.error?.code;
  return typeof code === "string" ? code : "UNKNOWN";
}

function goTo(path: string): void {
  window.location.replace(path);
}

/**
 * Starts the platform session, then goes on to `next` (checked again here), or to the refusal page
 * with the reason. The ref makes sure only one start is sent, even under React's strict mode.
 */
export function SessionStart({
  next,
  run = startFromBrowser,
  navigate = goTo,
}: {
  next: string;
  run?: () => Promise<StartResult>;
  navigate?: (path: string) => void;
}) {
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void run().then((result) => {
      if (result.ok) navigate(safeNextPath(next));
      else navigate(`/session-required?code=${encodeURIComponent(result.code)}`);
    });
  }, [next, run, navigate]);
  return (
    <p role="status" className="mt-4 text-body">
      Starting a platform session…
    </p>
  );
}
