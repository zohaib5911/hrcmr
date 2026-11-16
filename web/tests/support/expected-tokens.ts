import { brand } from "@brand";

/**
 * The colour tokens the design plan (section 5.3) asks for, with the few documented changes made so
 * that every pair passes WCAG AA. Shared by the unit tests (which check globals.css) and the browser
 * tests (which check what the page actually renders).
 */

// ---- The plan's table (section 5.3), as written ------------------------------------------------

export const PLAN_LIGHT: Record<string, string> = {
  "--bg": "#F5F5F7",
  "--bg-elevated": "#FFFFFF",
  "--bg-grouped": "#F2F2F7",
  "--fill-secondary": "rgba(120,120,128,0.12)",
  "--label": "#1D1D1F",
  "--label-secondary": "#6E6E73",
  "--label-tertiary": "#86868B",
  "--separator": "rgba(60,60,67,0.18)",
  "--accent": "#0071E3",
  "--accent-pressed": "#0062C4",
  "--success": "#248A3D",
  "--success-fill": "#34C759",
  "--warning": "#B25000",
  "--warning-fill": "#FF9F0A",
  "--danger": "#D70015",
  "--danger-fill": "#FF3B30",
  "--info": "#0071E3",
  "--sidebar-material": "rgba(246,246,248,0.72)",
};

export const PLAN_DARK: Record<string, string> = {
  "--bg": "#000000",
  "--bg-elevated": "#1C1C1E",
  "--bg-grouped": "#000000",
  "--fill-secondary": "rgba(120,120,128,0.24)",
  "--label": "#F5F5F7",
  "--label-secondary": "#A1A1A6",
  "--label-tertiary": "#6E6E73",
  "--separator": "rgba(84,84,88,0.6)",
  "--accent": "#2997FF",
  "--accent-pressed": "#0A84FF",
  "--success": "#30D158",
  "--success-fill": "#30D158",
  "--warning": "#FFD60A",
  "--warning-fill": "#FFD60A",
  "--danger": "#FF453A",
  "--danger-fill": "#FF453A",
  "--info": "#64D2FF",
  "--sidebar-material": "rgba(28,28,30,0.72)",
};

/**
 * Where the plan's own value fails its own rule ("every pair must pass WCAG AA"), the nearest
 * passing value is used. Each entry is a decision recorded in PROGRESS.md (decision 30). No other
 * plan value may differ.
 */
export const DEVIATIONS = {
  light: {
    "--success": "#1F7835", // plan #248A3D: 4.4:1 on white, 3.6:1 on its own chip
    "--warning": "#AC4D00", // plan #B25000: 4.3:1 on its chip over the canvas
    "--danger": "#CC0014", // plan #D70015: 4.1:1 on its chip over the canvas
    "--info": "#0062C6", // plan #0071E3: 3.6:1 on its chip (the fill keeps #0071E3)
  },
  dark: {
    "--danger": "#FF4B40", // plan #FF453A: 4.4:1 on its chip over cards (the fill keeps #FF453A)
  },
} as const;

/** Tokens the plan does not list, which the pairs above need (see PROGRESS.md decision 30). */
const ADDED_LIGHT: Record<string, string> = {
  "--avatar-accent": "#e0dbf5",
  "--avatar-success": "#e3dbf5",
  "--avatar-warning": "#e6dbf5",
  "--avatar-danger": "#eadbf5",
  "--avatar-info": "#eddbf5",
  "--avatar-neutral": "#f0dbf5",

  "--placeholder": "#636366", // the plan's #6E6E73 is 4.0:1 on an input fill over the canvas
  "--accent-text": "color-mix(in srgb, var(--accent) 85%, black)",
  "--accent-tint": "color-mix(in srgb, var(--accent) 12%, transparent)",
  "--on-accent": "#FFFFFF",
  "--on-fixed": "#FFFFFF",
  "--fixed-admin": "#B00010",
  "--scrim": "rgba(0,0,0,0.4)",
  "--knob": "#FFFFFF",
  "--info-fill": "#0071E3",
  "--success-tint": "color-mix(in srgb, var(--success-fill) 12%, transparent)",
  "--warning-tint": "color-mix(in srgb, var(--warning-fill) 12%, transparent)",
  "--danger-tint": "color-mix(in srgb, var(--danger-fill) 12%, transparent)",
  "--info-tint": "color-mix(in srgb, var(--info-fill) 12%, transparent)",
  "--sidebar-material-solid": "#F6F6F8",
  "--glass-thin": "color-mix(in srgb, var(--bg-elevated) 55%, transparent)",
  "--glass-regular": "color-mix(in srgb, var(--bg-elevated) 70%, transparent)",
  "--glass-thick": "color-mix(in srgb, var(--bg-elevated) 82%, transparent)",
  "--glass-stroke": "rgba(255,255,255,0.6)",
  "--glass-highlight": "rgba(255,255,255,0.8)",
  "--glass-shadow": "0 8px 32px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)",
  "--backdrop-tint": "color-mix(in srgb, var(--accent) 8%, transparent)",
  "--e1": "0 1px 2px rgba(0,0,0,0.04), 0 1px 1px rgba(0,0,0,0.02)",
  "--e2": "0 4px 12px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)",
  "--e3": "0 20px 50px rgba(0,0,0,0.12), 0 4px 12px rgba(0,0,0,0.06)",
};

const DARK_RING = "0 0 0 1px rgba(255,255,255,0.08)"; // plan 5.4: borders, not shadows, in dark
const ADDED_DARK: Record<string, string> = {
  "--avatar-accent": "#241957",
  "--avatar-success": "#2c1957",
  "--avatar-warning": "#341957",
  "--avatar-danger": "#3c1957",
  "--avatar-info": "#441957",
  "--avatar-neutral": "#4d1957",

  "--placeholder": "#A1A1A6",
  "--accent-text": "var(--accent)",
  "--accent-tint": "color-mix(in srgb, var(--accent) 12%, transparent)",
  "--on-accent": "#000000",
  "--on-fixed": "#FFFFFF",
  "--fixed-admin": "#B00010",
  "--scrim": "rgba(0,0,0,0.6)",
  "--knob": "#FFFFFF",
  "--info-fill": "#64D2FF",
  "--success-tint": "color-mix(in srgb, var(--success-fill) 12%, transparent)",
  "--warning-tint": "color-mix(in srgb, var(--warning-fill) 12%, transparent)",
  "--danger-tint": "color-mix(in srgb, var(--danger-fill) 12%, transparent)",
  "--info-tint": "color-mix(in srgb, var(--info-fill) 12%, transparent)",
  "--sidebar-material-solid": "#1C1C1E",
  "--glass-thin": "color-mix(in srgb, var(--bg-elevated) 55%, transparent)",
  "--glass-regular": "color-mix(in srgb, var(--bg-elevated) 70%, transparent)",
  "--glass-thick": "color-mix(in srgb, var(--bg-elevated) 82%, transparent)",
  "--glass-stroke": "rgba(255,255,255,0.14)",
  "--glass-highlight": "rgba(255,255,255,0.1)",
  "--glass-shadow": "0 8px 32px rgba(0,0,0,0.5)",
  "--backdrop-tint": "color-mix(in srgb, var(--accent) 20%, transparent)",
  "--e1": DARK_RING,
  "--e2": DARK_RING,
  "--e3": DARK_RING,
};

const expected = (
  plan: Record<string, string>,
  deviations: Record<string, string>,
  added: Record<string, string>,
) => ({ ...plan, ...deviations, ...added }) as Record<string, string>;

export const EXPECTED_LIGHT = expected(PLAN_LIGHT, DEVIATIONS.light, ADDED_LIGHT);
export const EXPECTED_DARK = expected(PLAN_DARK, DEVIATIONS.dark, ADDED_DARK);

export const BRANDED_LIGHT = {
  ...EXPECTED_LIGHT,
  "--accent": brand.colours.accent,
  "--accent-pressed": `color-mix(in srgb, ${brand.colours.accent} 86%, black)`,
  "--accent-text": `color-mix(in srgb, ${brand.colours.accent} 85%, black)`,
};
export const BRANDED_DARK = {
  ...EXPECTED_DARK,
  "--accent": brand.colours.accentDark,
  "--accent-pressed": `color-mix(in srgb, ${brand.colours.accentDark} 86%, black)`,
  "--accent-text": brand.colours.accentDark,
};
