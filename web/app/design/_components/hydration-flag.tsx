"use client";

import { useEffect } from "react";

/**
 * Marks <html data-hydrated> once React has taken over the page, so a browser test can wait for it
 * instead of guessing with a delay. Before that moment a click or a focus lands on markup that has no
 * event handlers yet. Development page only.
 */
export function HydrationFlag() {
  useEffect(() => {
    document.documentElement.setAttribute("data-hydrated", "true");
  }, []);
  return null;
}
