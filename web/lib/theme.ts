/**
 * Light / dark / system (plan.md 5.3). The choice lives in a cookie, so the server can stamp
 * `data-theme` on <html> before the first byte of HTML is sent: no flash of the wrong theme and no
 * inline script (which the strict Content-Security-Policy would block).
 *
 * "system" is the default and means: no cookie, no attribute, follow `prefers-color-scheme`.
 */

export const THEME_COOKIE = "theme";

export type ThemeChoice = "system" | "light" | "dark";

/** Anything that is not exactly "light" or "dark" is the system setting; a bad cookie changes nothing. */
export function parseTheme(value: string | null | undefined): ThemeChoice {
  return value === "light" || value === "dark" ? value : "system";
}

/** The `data-theme` value for <html>, or `undefined` to follow the system. */
export function themeAttribute(choice: ThemeChoice): "light" | "dark" | undefined {
  return choice === "system" ? undefined : choice;
}

const YEAR_IN_SECONDS = 365 * 24 * 60 * 60;

/** The `document.cookie` string for a choice. "system" removes the cookie. */
export function themeCookie(choice: ThemeChoice, secure: boolean): string {
  const attributes = ["Path=/", "SameSite=Lax", ...(secure ? ["Secure"] : [])];
  return choice === "system"
    ? [`${THEME_COOKIE}=`, "Max-Age=0", ...attributes].join("; ")
    : [`${THEME_COOKIE}=${choice}`, `Max-Age=${YEAR_IN_SECONDS}`, ...attributes].join("; ");
}
