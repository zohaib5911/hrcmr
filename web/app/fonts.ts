/**
 * Inter, self-hosted (plan.md 5.2). The font files come from the `@fontsource-variable/inter` package
 * (SIL Open Font License), are copied into the build by next/font, and are served from this site:
 * no request to Google or any other font host.
 *
 * The system UI font comes first in the stack (globals.css), so Apple devices show their own font and
 * every other device shows Inter. Two files cover Western European names (latin) and the Polish,
 * Romanian, Turkish and other names common in UK workforces (latin-ext). The second is fetched only
 * when a page actually contains one of those letters.
 */
import localFont from "next/font/local";

export const inter = localFont({
  src: "../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  variable: "--font-inter",
  weight: "100 900",
  style: "normal",
  display: "swap",
  // Make the fallback font take the same space as Inter, so text does not jump when Inter loads.
  adjustFontFallback: "Arial",
});

export const interExtended = localFont({
  src: "../node_modules/@fontsource-variable/inter/files/inter-latin-ext-wght-normal.woff2",
  variable: "--font-inter-ext",
  weight: "100 900",
  style: "normal",
  display: "swap",
  preload: false,
  adjustFontFallback: false,
});
