"use client";

import { RouteError, type RouteErrorProps } from "@/components/app/route-error";

export default function AppError(props: RouteErrorProps) {
  return <RouteError {...props} homeHref="/dashboard" homeLabel="Go to the dashboard" />;
}
