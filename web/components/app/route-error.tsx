"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

import { ErrorState } from "@/components/ui/error-state";

export interface RouteErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * What a person sees when a page fails to render (C6.1.10): plain words, a way to try again, a way
 * home, and the reference support can look up. The error itself goes to Sentry, never on screen.
 */
export function RouteError({
  error,
  reset,
  homeHref = "/",
  homeLabel = "Go to the home page",
  report = Sentry.captureException,
}: RouteErrorProps & {
  homeHref?: string;
  homeLabel?: string;
  report?: (error: unknown) => unknown;
}) {
  useEffect(() => {
    report(error);
  }, [error, report]);

  return (
    <div className="flex flex-col items-center pb-12">
      <ErrorState
        headingLevel={1}
        message="This page could not be shown. Try again; if it keeps happening, contact support and quote the reference."
        onRetry={reset}
        {...(error.digest ? { requestId: error.digest } : {})}
      />
      {/* A plain anchor: after a failed render the router itself may be what broke. */}
      <a href={homeHref} className="text-accent-text text-body font-medium hover:underline">
        {homeLabel}
      </a>
    </div>
  );
}
