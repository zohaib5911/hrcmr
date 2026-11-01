import { themeAttribute, themeCookie, type ThemeChoice } from "./theme";

/** The parts of `document` that changing the theme touches (so tests can pass a stand-in). */
export interface ThemeTarget {
  cookie: string;
  readonly documentElement: Pick<HTMLElement, "setAttribute" | "removeAttribute">;
}

/**
 * Saves the choice in the cookie (the server reads it on the next request) and applies it to
 * <html> at once. "System" removes the cookie and the attribute.
 */
export function applyTheme(choice: ThemeChoice, target: ThemeTarget, secure: boolean): void {
  target.cookie = themeCookie(choice, secure);
  const attribute = themeAttribute(choice);
  if (attribute) target.documentElement.setAttribute("data-theme", attribute);
  else target.documentElement.removeAttribute("data-theme");
}
