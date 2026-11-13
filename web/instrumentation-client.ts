import * as Sentry from "@sentry/nextjs";

import { privacyOptions } from "./lib/security/telemetry";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN_WEB;
if (dsn) {
  Sentry.init({
    dsn,
    ...privacyOptions,
    integrations: [Sentry.globalHandlersIntegration()],
    // No session replay, console capture, network breadcrumbs or performance traces.
  });
}
