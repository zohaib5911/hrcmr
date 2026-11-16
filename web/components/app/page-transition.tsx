"use client";

import { usePathname } from "next/navigation";
import { ViewTransition, type ReactNode } from "react";

/**
 * A short cross-fade when the page changes (U6.1.9), through the browser's View Transitions API
 * where it exists; elsewhere the page simply swaps. Only the page content takes part (the shell
 * stays still). Timings and the reduced-motion switch are in app/globals.css (`.page-fade`).
 */
export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <ViewTransition key={pathname} enter="page-fade" exit="page-fade" default="none">
      {children}
    </ViewTransition>
  );
}
