"use client";

import { useEffect, useRef } from "react";

interface TurnstileApi {
  render: (
    element: HTMLElement,
    options: {
      sitekey: string;
      size: "flexible";
      theme: "auto";
      callback: (token: string) => void;
      "expired-callback": () => void;
      "error-callback": () => void;
    },
  ) => string;
  reset: (widgetId: string) => void;
  remove: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

/** The public site key. Without one (a developer's machine) the check is switched off on both sides. */
export const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || undefined;

let loading: Promise<TurnstileApi> | undefined;

function load(): Promise<TurnstileApi> {
  loading ??= new Promise((resolve, reject) => {
    if (window.turnstile) return resolve(window.turnstile);
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.async = true;
    script.onload = () =>
      window.turnstile ? resolve(window.turnstile) : reject(new Error("Turnstile did not start"));
    script.onerror = () => {
      loading = undefined;
      reject(new Error("Turnstile could not be loaded"));
    };
    document.head.append(script);
  });
  return loading;
}

interface TurnstileProps {
  /** Called with a one-time token, and with `null` when it expires or the check fails. */
  onToken: (token: string | null) => void;
  /** Change this number to ask for a fresh check (a token works once). */
  resetKey?: number;
}

/** Cloudflare Turnstile, shown only when a site key is set. */
export function Turnstile({ onToken, resetKey = 0 }: TurnstileProps) {
  const host = useRef<HTMLDivElement>(null);
  const widget = useRef<string | undefined>(undefined);
  const report = useRef(onToken);
  useEffect(() => {
    report.current = onToken;
  });

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY || !host.current) return;
    let cancelled = false;
    const element = host.current;
    load()
      .then((api) => {
        if (cancelled) return;
        widget.current = api.render(element, {
          sitekey: TURNSTILE_SITE_KEY,
          size: "flexible",
          theme: "auto",
          callback: (token) => report.current(token),
          "expired-callback": () => report.current(null),
          "error-callback": () => report.current(null),
        });
      })
      .catch(() => report.current(null));
    return () => {
      cancelled = true;
      if (widget.current) window.turnstile?.remove(widget.current);
      widget.current = undefined;
    };
  }, []);

  useEffect(() => {
    if (resetKey > 0 && widget.current) {
      window.turnstile?.reset(widget.current);
      report.current(null);
    }
  }, [resetKey]);

  if (!TURNSTILE_SITE_KEY) return null;
  return <div ref={host} className="min-h-16" data-testid="turnstile" />;
}
