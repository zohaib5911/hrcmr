"use client";

import { RouteError, type RouteErrorProps } from "@/components/app/route-error";

export default function PlatformError(props: RouteErrorProps) {
  return <RouteError {...props} homeLabel="Go to the admin home" />;
}
