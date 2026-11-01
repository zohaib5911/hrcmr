"use client";

import { useState } from "react";

import type { ThemeChoice } from "@/lib/theme";
import { applyTheme } from "@/lib/theme-dom";

const OPTIONS: readonly { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

/**
 * Chooses the colour theme (plan.md 5.3). The choice is saved in a cookie, so the server renders
 * the next page already in the right theme, and applied to <html> at once. "System" removes both.
 */
export function ThemeSwitch({ initial }: { initial: ThemeChoice }) {
  const [choice, setChoice] = useState<ThemeChoice>(initial);

  function select(next: ThemeChoice) {
    applyTheme(next, document, window.location.protocol === "https:");
    setChoice(next);
  }

  return (
    <fieldset className="bg-fill-secondary rounded-control inline-flex gap-0.5 p-0.5">
      <legend className="sr-only">Colour theme</legend>
      {OPTIONS.map(({ value, label }) => (
        <label key={value} className="relative">
          <input
            type="radio"
            name="theme"
            value={value}
            checked={choice === value}
            onChange={() => select(value)}
            className="peer sr-only"
          />
          <span className="text-callout text-label peer-checked:bg-elevated peer-checked:shadow-e1 motion-micro hit-target rounded-control peer-focus-visible:outline-accent inline-flex cursor-pointer items-center px-3 font-medium transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2">
            {label}
          </span>
        </label>
      ))}
    </fieldset>
  );
}
