/**
 * Motion presets (plan.md 5.5), in the shape Framer Motion takes, so they can be passed straight to
 * `transition`, `variants` and `initial`/`animate`. This module has no dependencies.
 *
 * Reduced motion: every preset has a reduced form that fades and never moves, scales or slides.
 * Callers pass `reduced` from `useReducedMotion()`.
 *
 * The same durations exist as CSS variables in app/globals.css (a test keeps them equal).
 */

export const SPRING = { type: "spring", stiffness: 420, damping: 34, mass: 0.9 } as const;

/** Seconds, as Framer Motion expects. */
export const DURATION = { micro: 0.12, small: 0.2, sheet: 0.32 } as const;

const FADE_TRANSITION = { duration: DURATION.small, ease: "easeOut" } as const;

export const fade = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
} as const;

interface SheetOptions {
  /** Below 768 px: the sheet rises from the bottom edge. */
  readonly mobile: boolean;
  readonly reduced: boolean;
}

/** Sheets and dialogs: rise on mobile, scale 0.96 plus fade on desktop, fade only when reduced. */
export function sheet({ mobile, reduced }: SheetOptions) {
  if (reduced) return fade;
  return mobile
    ? ({ hidden: { y: "100%" }, visible: { y: 0 } } as const)
    : ({ hidden: { opacity: 0, scale: 0.96 }, visible: { opacity: 1, scale: 1 } } as const);
}

/** List rows and cards entering: a short rise (8 px, the plan's maximum for scroll reveals). */
const RISE_IN = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0 },
} as const;

export function presets(reduced: boolean) {
  return {
    transition: reduced ? FADE_TRANSITION : SPRING,
    riseIn: reduced ? fade : RISE_IN,
  };
}

/** KPI numbers count up once on first view; with reduced motion they appear at their final value. */
export function countUpSeconds(reduced: boolean): number {
  return reduced ? 0 : 0.8;
}
