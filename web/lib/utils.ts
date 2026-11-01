import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

import { MARKETING_STYLES, RADII, TYPE_STYLES } from "./design/catalog";

/**
 * tailwind-merge resolves conflicts between Tailwind classes ("p-2 p-4" is just "p-4"). It only knows
 * Tailwind's own names, so the design system's text sizes, radii and elevations are declared here.
 * Without this, `text-callout` is read as a text COLOUR and silently removes the real colour class.
 */
const merge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: [...TYPE_STYLES, ...MARKETING_STYLES].map((style) => style.key) }],
      rounded: [{ rounded: RADII.map((radius) => radius.key) }],
      shadow: [{ shadow: ["e1", "e2", "e3"] }],
    },
  },
});

/** Joins class names and resolves conflicting Tailwind utilities (the last one wins). */
export function cn(...inputs: ClassValue[]): string {
  return merge(clsx(inputs));
}
