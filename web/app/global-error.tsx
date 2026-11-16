"use client";

import { RouteError, type RouteErrorProps } from "@/components/app/route-error";

import "./globals.css";

/** The last resort: the root layout itself failed, so this page brings its own html and body. */
export default function GlobalError(props: RouteErrorProps) {
  return (
    <html lang="en-GB">
      <body>
        <main>
          <RouteError {...props} />
        </main>
      </body>
    </html>
  );
}
