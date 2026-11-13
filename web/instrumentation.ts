import * as Sentry from "@sentry/nextjs";

import { privacyOptions } from "./lib/security/telemetry";

export function register() {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN_WEB;
  if (dsn) Sentry.init({ dsn, ...privacyOptions });
}

export const onRequestError = Sentry.captureRequestError;
