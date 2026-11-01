/**
 * The design system's inventory (plan.md section 5): every token, the type scale, radii,
 * elevations and the colour pairs that must meet WCAG AA.
 *
 * The CSS in app/globals.css is the source of truth for VALUES. This file is the source of truth for
 * WHAT EXISTS. Unit tests check that the two agree exactly, so the /design page, which renders
 * this list, always shows every token and nothing that does not exist.
 *
 * Class names are written out in full (never built from strings) so Tailwind can find them.
 */

export type TokenGroup = "surface" | "text" | "accent" | "status" | "material";

export interface ColourToken {
  readonly name: string;
  /** A Tailwind class that paints a swatch with this token. */
  readonly swatch: string;
  readonly group: TokenGroup;
  readonly use: string;
}

export const COLOUR_TOKENS: readonly ColourToken[] = [
  { name: "--bg", swatch: "bg-canvas", group: "surface", use: "App canvas" },
  { name: "--bg-elevated", swatch: "bg-elevated", group: "surface", use: "Cards and sheets" },
  { name: "--bg-grouped", swatch: "bg-grouped", group: "surface", use: "Settings-style lists" },
  {
    name: "--fill-secondary",
    swatch: "bg-fill-secondary",
    group: "surface",
    use: "Inputs and the segmented-control track",
  },
  { name: "--label", swatch: "bg-label", group: "text", use: "Primary text" },
  { name: "--label-secondary", swatch: "bg-label-secondary", group: "text", use: "Secondary text" },
  {
    name: "--label-tertiary",
    swatch: "bg-label-tertiary",
    group: "text",
    use: "Hints; large text and icons only",
  },
  {
    name: "--placeholder",
    swatch: "bg-placeholder",
    group: "text",
    use: "Input placeholder text (darker than the secondary label so it passes AA on an input fill)",
  },
  { name: "--separator", swatch: "bg-separator", group: "surface", use: "Hairlines" },
  { name: "--accent", swatch: "bg-accent", group: "accent", use: "Primary buttons and focus ring" },
  { name: "--accent-pressed", swatch: "bg-accent-pressed", group: "accent", use: "Pressed state" },
  {
    name: "--accent-text",
    swatch: "bg-accent-text",
    group: "accent",
    use: "Links and small accent text",
  },
  {
    name: "--on-accent",
    swatch: "bg-on-accent",
    group: "accent",
    use: "Text and icons on the accent colour",
  },
  { name: "--success", swatch: "bg-success", group: "status", use: "Verified, present (text)" },
  { name: "--success-fill", swatch: "bg-success-fill", group: "status", use: "Success fills" },
  { name: "--success-tint", swatch: "bg-success-tint", group: "status", use: "Success chip" },
  { name: "--warning", swatch: "bg-warning", group: "status", use: "Expiring, due (text)" },
  { name: "--warning-fill", swatch: "bg-warning-fill", group: "status", use: "Warning fills" },
  { name: "--warning-tint", swatch: "bg-warning-tint", group: "status", use: "Warning chip" },
  {
    name: "--danger",
    swatch: "bg-danger",
    group: "status",
    use: "Expired, failed, overdue (text)",
  },
  { name: "--danger-fill", swatch: "bg-danger-fill", group: "status", use: "Danger fills" },
  { name: "--danger-tint", swatch: "bg-danger-tint", group: "status", use: "Danger chip" },
  { name: "--info", swatch: "bg-info", group: "status", use: "Neutral notices (text)" },
  { name: "--info-fill", swatch: "bg-info-fill", group: "status", use: "Info fills" },
  { name: "--info-tint", swatch: "bg-info-tint", group: "status", use: "Info chip" },
  {
    name: "--sidebar-material",
    swatch: "bg-sidebar-material",
    group: "material",
    use: "Sidebar and toolbar, over a blur",
  },
  {
    name: "--sidebar-material-solid",
    swatch: "bg-sidebar-solid",
    group: "material",
    use: "Solid stand-in when blur is unavailable or transparency is reduced",
  },
];

export interface Elevation {
  readonly name: string;
  readonly shadow: string;
  readonly use: string;
}

export const ELEVATIONS: readonly Elevation[] = [
  { name: "--e1", shadow: "shadow-e1", use: "Cards at rest" },
  { name: "--e2", shadow: "shadow-e2", use: "Raised cards, popovers" },
  { name: "--e3", shadow: "shadow-e3", use: "Sheets and dialogs" },
];

/** Every custom property each theme must define. */
export const THEME_TOKEN_NAMES: readonly string[] = [
  ...COLOUR_TOKENS.map((token) => token.name),
  ...ELEVATIONS.map((elevation) => elevation.name),
];

// --- Typography (plan 5.2) -----------------------------------------------------------------------

export interface TypeStyle {
  readonly key: string;
  readonly label: string;
  /** The Tailwind class that applies size, line height, weight and tracking together. */
  readonly utility: string;
  /** The plan's numbers: px, px, weight, tracking in px. */
  readonly size: number;
  readonly lineHeight: number;
  readonly weight: number;
  readonly tracking: number;
}

export const TYPE_STYLES: readonly TypeStyle[] = [
  {
    key: "large-title",
    label: "Large Title",
    utility: "text-large-title",
    size: 34,
    lineHeight: 41,
    weight: 700,
    tracking: -0.4,
  },
  {
    key: "title-1",
    label: "Title 1",
    utility: "text-title-1",
    size: 28,
    lineHeight: 34,
    weight: 700,
    tracking: -0.4,
  },
  {
    key: "title-2",
    label: "Title 2",
    utility: "text-title-2",
    size: 22,
    lineHeight: 28,
    weight: 600,
    tracking: -0.3,
  },
  {
    key: "title-3",
    label: "Title 3",
    utility: "text-title-3",
    size: 20,
    lineHeight: 25,
    weight: 600,
    tracking: -0.2,
  },
  {
    key: "headline",
    label: "Headline",
    utility: "text-headline",
    size: 15,
    lineHeight: 20,
    weight: 600,
    tracking: -0.1,
  },
  {
    key: "body",
    label: "Body",
    utility: "text-body",
    size: 15,
    lineHeight: 22,
    weight: 400,
    tracking: 0,
  },
  {
    key: "callout",
    label: "Callout",
    utility: "text-callout",
    size: 14,
    lineHeight: 20,
    weight: 400,
    tracking: 0,
  },
  {
    key: "subheadline",
    label: "Subheadline",
    utility: "text-subheadline",
    size: 13,
    lineHeight: 18,
    weight: 400,
    tracking: 0,
  },
  {
    key: "footnote",
    label: "Footnote",
    utility: "text-footnote",
    size: 12,
    lineHeight: 16,
    weight: 400,
    tracking: 0,
  },
  {
    key: "caption",
    label: "Caption",
    utility: "text-caption",
    size: 11,
    lineHeight: 13,
    weight: 500,
    tracking: 0.1,
  },
];

export interface MarketingStyle {
  readonly key: string;
  readonly label: string;
  readonly utility: string;
  /** The plan's range, reached between a 1024 px and a 1440 px wide viewport (px). */
  readonly desktopMin: number;
  readonly desktopMax: number;
  /** The smallest size, on phones (px). `clamp()` scales between this and `desktopMax`. */
  readonly floor: number;
}

export const MARKETING_STYLES: readonly MarketingStyle[] = [
  { key: "hero", label: "Hero", utility: "text-hero", desktopMin: 64, desktopMax: 80, floor: 40 },
  {
    key: "section",
    label: "Section title",
    utility: "text-section",
    desktopMin: 40,
    desktopMax: 48,
    floor: 28,
  },
  {
    key: "lead",
    label: "Lead paragraph",
    utility: "text-lead",
    desktopMin: 19,
    desktopMax: 21,
    floor: 19,
  },
];

// --- Shape and space (plan 5.4) ------------------------------------------------------------------

export interface Radius {
  readonly key: string;
  readonly px: number;
  readonly utility: string;
  readonly use: string;
}

export const RADII: readonly Radius[] = [
  { key: "control", px: 10, utility: "rounded-control", use: "Buttons, inputs" },
  { key: "popover", px: 14, utility: "rounded-popover", use: "Menus, popovers" },
  { key: "card", px: 16, utility: "rounded-card", use: "Cards" },
  { key: "sheet", px: 20, utility: "rounded-sheet", use: "Sheets and dialogs" },
  { key: "pill", px: 999, utility: "rounded-pill", use: "Chips, pills, avatars" },
];

/** The 4 px grid: Tailwind's spacing unit is 0.25rem, so `w-N` is N x 4 px. */
export const SPACING_STEPS = [
  { step: 1, px: 4, bar: "w-1" },
  { step: 2, px: 8, bar: "w-2" },
  { step: 3, px: 12, bar: "w-3" },
  { step: 4, px: 16, bar: "w-4" },
  { step: 6, px: 24, bar: "w-6" },
  { step: 8, px: 32, bar: "w-8" },
  { step: 12, px: 48, bar: "w-12" },
  { step: 16, px: 64, bar: "w-16" },
] as const;

// --- Accessibility (plan 5.3, 0.1 rule 10) --------------------------------------------------------

/**
 * Colour pairs that must meet WCAG AA in BOTH themes. `over` is the surface a translucent
 * background is painted on. `min` is 4.5 for text and 3 for large text and UI.
 */
export interface ContrastPair {
  readonly fg: string;
  readonly bg: string;
  readonly over?: string;
  readonly min: 3 | 4.5;
  readonly use: string;
}

const SURFACES = ["--bg", "--bg-elevated", "--bg-grouped"] as const;

const STATUS = [
  { text: "--success", tint: "--success-tint" },
  { text: "--warning", tint: "--warning-tint" },
  { text: "--danger", tint: "--danger-tint" },
  { text: "--info", tint: "--info-tint" },
] as const;

export const CONTRAST_PAIRS: readonly ContrastPair[] = [
  ...SURFACES.flatMap((bg): ContrastPair[] => [
    { fg: "--label", bg, min: 4.5, use: "Primary text" },
    { fg: "--label-secondary", bg, min: 4.5, use: "Secondary text" },
    { fg: "--label-tertiary", bg, min: 3, use: "Hints (large text and icons only)" },
    { fg: "--accent-text", bg, min: 4.5, use: "Links" },
    { fg: "--accent", bg, min: 3, use: "Focus ring and accent icons" },
    ...STATUS.map(({ text }): ContrastPair => ({ fg: text, bg, min: 4.5, use: "Status text" })),
    ...STATUS.map(({ text, tint }): ContrastPair => ({
      fg: text,
      bg: tint,
      over: bg,
      min: 4.5,
      use: "Status chip",
    })),
  ]),
  { fg: "--on-accent", bg: "--accent", min: 4.5, use: "Primary button label" },
  { fg: "--on-accent", bg: "--accent-pressed", min: 4.5, use: "Primary button label, pressed" },
  ...SURFACES.flatMap((over): ContrastPair[] => [
    { fg: "--label", bg: "--fill-secondary", over, min: 4.5, use: "Input text" },
    { fg: "--placeholder", bg: "--fill-secondary", over, min: 4.5, use: "Input placeholder" },
  ]),
  { fg: "--label", bg: "--sidebar-material", over: "--bg", min: 4.5, use: "Sidebar text" },
  {
    fg: "--label-secondary",
    bg: "--sidebar-material",
    over: "--bg",
    min: 4.5,
    use: "Sidebar caption",
  },
];
