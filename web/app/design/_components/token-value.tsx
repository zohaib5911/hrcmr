"use client";

import { useState, useSyncExternalStore } from "react";

import { formatColour, parseComputedColour } from "@/lib/design/contrast";

/** Re-read whenever the theme changes: the user's choice (data-theme) or the system setting. */
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", onChange);
  return () => {
    observer.disconnect();
    media.removeEventListener("change", onChange);
  };
}

/**
 * The colour a token resolves to in the theme of the surrounding scope, as the browser paints it,
 * written like the plan's table (`#F5F5F7`, `rgba(120, 120, 128, 0.12)`). Derived tokens such as the
 * accent link colour show their real result, and a build that shortens `#000000` to `#000` is
 * invisible here.
 */
export function TokenValue({ token }: { token: string }) {
  const [element, setElement] = useState<HTMLElement | null>(null);
  const value = useSyncExternalStore(
    subscribe,
    () => {
      const swatch = element?.closest("[data-theme]")?.querySelector(`[data-swatch="${token}"]`);
      return swatch
        ? formatColour(parseComputedColour(getComputedStyle(swatch).backgroundColor))
        : "";
    },
    () => "",
  );
  return (
    <code ref={setElement} data-token-value={token}>
      {value || "\u2026"}
    </code>
  );
}
