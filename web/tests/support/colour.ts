/**
 * Evaluates the few colour forms the design tokens use, without a browser. Pure (no file access),
 * so both the unit tests and the Playwright tests can use it.
 */
import { composite, mixSrgb, parseColour, type Rgba } from "../../lib/design/contrast";

/** Follows `var(--x)` and evaluates `color-mix(in srgb, A n%, black|transparent)`. */
export function resolveColour(name: string, tokens: Map<string, string>): Rgba {
  const raw = tokens.get(name);
  if (raw === undefined) throw new Error(`${name} is not defined`);
  return evaluate(raw, tokens);
}

function evaluate(raw: string, tokens: Map<string, string>): Rgba {
  const value = raw.trim();
  const variable = /^var\((--[a-z0-9-]+)\)$/.exec(value);
  if (variable?.[1]) return resolveColour(variable[1], tokens);

  const mix =
    /^color-mix\(in srgb,\s*(.+?)\s+(\d+(?:\.\d+)?)%,\s*(black|white|transparent)\)$/.exec(value);
  if (mix?.[1] && mix[2] && mix[3]) {
    const first = evaluate(mix[1], tokens);
    const weight = Number(mix[2]) / 100;
    if (mix[3] === "transparent") return { ...first, a: first.a * weight };
    const other = parseColour(mix[3] === "black" ? "#000000" : "#ffffff");
    return mixSrgb(first, other, weight);
  }
  return parseColour(value);
}

/** The colour as it looks on screen: translucent colours are laid over `over` first. */
export function visibleColour(name: string, tokens: Map<string, string>, over?: string): Rgba {
  const colour = resolveColour(name, tokens);
  if (colour.a === 1) return colour;
  if (!over) throw new Error(`${name} is translucent: say which surface it is on`);
  return composite(colour, visibleColour(over, tokens));
}
