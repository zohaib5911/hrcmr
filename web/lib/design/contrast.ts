/**
 * WCAG 2.2 contrast maths (plan.md 5.3: every text pair 4.5:1, every UI pair 3:1).
 *
 * Pure functions, no DOM. Used by the unit tests that guard the colour tokens and by the guard that
 * refuses a brand accent colour that would fail contrast.
 */

export interface Rgba {
  readonly r: number; // 0..255
  readonly g: number;
  readonly b: number;
  readonly a: number; // 0..1
}

const HEX = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;
const FUNCTIONAL = /^rgba?\(\s*([^)]+)\)$/i;

/** Parses `#rgb`, `#rrggbb`, `rgb(r, g, b)` and `rgba(r, g, b, a)`. Throws on anything else. */
export function parseColour(value: string): Rgba {
  const text = value.trim();
  const hex = HEX.exec(text);
  if (hex) {
    const digits = hex[1] ?? "";
    const full = digits.length === 3 ? [...digits].map((d) => d + d).join("") : digits;
    return {
      r: Number.parseInt(full.slice(0, 2), 16),
      g: Number.parseInt(full.slice(2, 4), 16),
      b: Number.parseInt(full.slice(4, 6), 16),
      a: 1,
    };
  }
  const fn = FUNCTIONAL.exec(text);
  if (fn) {
    const parts = (fn[1] ?? "")
      .split(/[\s,/]+/)
      .filter(Boolean)
      .map(Number);
    const [r, g, b, a = 1] = parts;
    if (r !== undefined && g !== undefined && b !== undefined && parts.every(Number.isFinite)) {
      return { r, g, b, a };
    }
  }
  throw new Error(`Unsupported colour: ${value}`);
}

/** `fg` painted over an opaque `bg`. */
export function composite(fg: Rgba, bg: Rgba): Rgba {
  const mix = (f: number, b: number) => f * fg.a + b * (1 - fg.a);
  return { r: mix(fg.r, bg.r), g: mix(fg.g, bg.g), b: mix(fg.b, bg.b), a: 1 };
}

/**
 * `color-mix(in srgb, a <weight>%, b)`, for opaque colours. Used to evaluate the few derived
 * tokens (accent text) without a browser.
 */
export function mixSrgb(a: Rgba, b: Rgba, weightA: number): Rgba {
  const mix = (x: number, y: number) => x * weightA + y * (1 - weightA);
  return { r: mix(a.r, b.r), g: mix(a.g, b.g), b: mix(a.b, b.b), a: 1 };
}

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(colour: Rgba): number {
  return 0.2126 * channel(colour.r) + 0.7152 * channel(colour.g) + 0.0722 * channel(colour.b);
}

/** Contrast ratio between two OPAQUE colours (composite translucent ones first). */
export function contrastRatio(a: Rgba, b: Rgba): number {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** `#rrggbb` for an opaque colour. */
export function toHex(colour: Rgba): string {
  const hex = (n: number) => Math.round(n).toString(16).padStart(2, "0");
  return `#${hex(colour.r)}${hex(colour.g)}${hex(colour.b)}`.toUpperCase();
}

/**
 * Reads a colour as a browser reports it from `getComputedStyle`: `rgb()` / `rgba()`, or
 * `color(srgb r g b / a)` (what `color-mix()` produces; components are 0 to 1).
 */
export function parseComputedColour(value: string): Rgba {
  const rgb = /^rgba?\(([^)]+)\)$/.exec(value.trim());
  if (rgb?.[1]) {
    const [r = 0, g = 0, b = 0, a = 1] = rgb[1]
      .split(/[\s,/]+/)
      .filter(Boolean)
      .map(Number);
    return { r, g, b, a };
  }
  const srgb = /^color\(srgb ([^)]+)\)$/.exec(value.trim());
  if (srgb?.[1]) {
    const [r = 0, g = 0, b = 0, a = 1] = srgb[1]
      .split(/[\s/]+/)
      .filter(Boolean)
      .map(Number);
    return { r: r * 255, g: g * 255, b: b * 255, a };
  }
  throw new Error(`Cannot read the computed colour: ${value}`);
}

/** `#RRGGBB` for an opaque colour, `rgba(r, g, b, a)` for a translucent one (as in the plan). */
export function formatColour(colour: Rgba): string {
  if (colour.a >= 0.999) return toHex(colour);
  const alpha = Number(colour.a.toFixed(2));
  return `rgba(${Math.round(colour.r)}, ${Math.round(colour.g)}, ${Math.round(colour.b)}, ${alpha})`;
}
