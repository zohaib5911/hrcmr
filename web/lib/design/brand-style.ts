/**
 * The brand accent (plan.md 5.3): `brand.config.ts` may override the accent colour and nothing else.
 *
 * `brandAccentCss` returns the CSS that applies it, or "" when the brand uses the defaults. It
 * validates the colours (so configuration can never inject CSS) and refuses any colour that would
 * fail WCAG AA, so changing the brand later cannot quietly make buttons or links unreadable.
 *
 * The CSS is rendered in a <style nonce> element: an inline `style=""` attribute would be blocked
 * by the Content-Security-Policy.
 */
import { composite, contrastRatio, parseColour, type Rgba } from "./contrast";

/** The accent colours in app/globals.css. A test keeps these equal to the stylesheet. */
export const DEFAULT_ACCENT = { light: "#0071E3", dark: "#2997FF" } as const;

export interface AccentConfig {
  readonly accent: string;
  readonly accentDark: string;
}

const HEX = /^#[0-9A-Fa-f]{6}$/;
const AA_TEXT = 4.5;

function requireHex(name: string, value: string): Rgba {
  if (!HEX.test(value)) {
    throw new Error(
      `brand.config.ts: ${name} must be a colour written as #rrggbb, got "${value}".`,
    );
  }
  return parseColour(value);
}

const WHITE = parseColour("#FFFFFF");
const BLACK = parseColour("#000000");
// The surfaces text sits on in each theme (plan 5.3).
const DARK_SURFACES = ["#000000", "#1C1C1E"].map(parseColour);

function ratio(a: Rgba, b: Rgba): number {
  return contrastRatio(composite(a, BLACK), composite(b, BLACK));
}

function check(condition: boolean, message: string): void {
  if (!condition) throw new Error(`brand.config.ts: ${message} WCAG AA needs ${AA_TEXT}:1.`);
}

export function brandAccentCss({ accent, accentDark }: AccentConfig): string {
  const light = requireHex("colours.accent", accent);
  const dark = requireHex("colours.accentDark", accentDark);
  if (
    accent.toUpperCase() === DEFAULT_ACCENT.light &&
    accentDark.toUpperCase() === DEFAULT_ACCENT.dark
  ) {
    return "";
  }

  // Light: the button label is white. (The link colour is the accent darkened 12%, which only
  // gets darker, so if white text is readable on the accent the link colour is too.)
  const whiteOnLight = ratio(WHITE, light);
  check(
    whiteOnLight >= AA_TEXT,
    `white text on colours.accent ${accent} is ${whiteOnLight.toFixed(2)}:1.`,
  );

  // Dark: the button label is black, and links use the accent itself on cards and the canvas.
  const blackOnDark = ratio(BLACK, dark);
  check(
    blackOnDark >= AA_TEXT,
    `black text on colours.accentDark ${accentDark} is ${blackOnDark.toFixed(2)}:1.`,
  );
  for (const surface of DARK_SURFACES) {
    check(
      ratio(dark, surface) >= AA_TEXT,
      `colours.accentDark ${accentDark} as link text is too dim on a dark surface.`,
    );
  }

  const lightRule = `--accent:${accent};--accent-pressed:color-mix(in srgb,${accent} 86%,black);--accent-text:color-mix(in srgb,${accent} 88%,black)`;
  const darkRule = `--accent:${accentDark};--accent-pressed:color-mix(in srgb,${accentDark} 86%,black);--accent-text:${accentDark}`;
  return [
    `:root,[data-theme="light"]{${lightRule}}`,
    `@media (prefers-color-scheme:dark){:root:not([data-theme]){${darkRule}}}`,
    `[data-theme="dark"]{${darkRule}}`,
  ].join("");
}
