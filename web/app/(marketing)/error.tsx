"use client";

import { RouteError, type RouteErrorProps } from "@/components/app/route-error";

export default function MarketingError(props: RouteErrorProps) {
  return (
    <main>
      <RouteError {...props} />
    </main>
  );
}
