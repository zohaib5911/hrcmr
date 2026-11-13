/** Diagnostic structure only. Never send request/user data or arbitrary error text. */
import type { ErrorEvent } from "@sentry/nextjs";

const symbol = /^[A-Za-z_$][A-Za-z0-9_.$<>-]{0,159}$/;

export function beforeSend(event: ErrorEvent): ErrorEvent {
  const clean: ErrorEvent = { type: undefined };
  if (event.event_id) clean.event_id = event.event_id;
  if (event.timestamp) clean.timestamp = event.timestamp;
  if (event.platform) clean.platform = event.platform;
  if (event.level) clean.level = event.level;
  if (event.exception?.values?.length) {
    clean.exception = {
      values: event.exception.values.map((error) => ({
        type: error.type && symbol.test(error.type) ? error.type : "Error",
        value: "[redacted]",
        stacktrace: {
          frames: (error.stacktrace?.frames ?? []).map((frame) => ({
            ...(frame.function && symbol.test(frame.function) ? { function: frame.function } : {}),
            ...(typeof frame.lineno === "number" ? { lineno: frame.lineno } : {}),
            ...(typeof frame.colno === "number" ? { colno: frame.colno } : {}),
          })),
        },
      })),
    };
  } else {
    clean.message = "[redacted]";
  }
  return clean;
}

export const privacyOptions = {
  sendDefaultPii: false,
  defaultIntegrations: false,
  tracesSampleRate: 0,
  maxBreadcrumbs: 0,
  beforeSend,
} as const;
