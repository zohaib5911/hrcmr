"use client";

import { RouteError, type RouteErrorProps } from "@/components/app/route-error";

export default function AuthError(props: RouteErrorProps) {
  return <RouteError {...props} homeHref="/login" homeLabel="Go to sign in" />;
}
