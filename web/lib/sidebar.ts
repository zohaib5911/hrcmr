/**
 * The sidebar's collapsed or expanded state (plan 5.6). Like the theme, it is a cookie, so the server
 * draws the sidebar at the right width in the first byte of HTML and the page never jumps.
 */

export const SIDEBAR_COOKIE = "sidebar";

export type SidebarState = "expanded" | "collapsed";

export function parseSidebar(value: string | null | undefined): SidebarState {
  return value === "collapsed" ? "collapsed" : "expanded";
}

const YEAR_IN_SECONDS = 365 * 24 * 60 * 60;

export function sidebarCookie(state: SidebarState, secure: boolean): string {
  return [
    `${SIDEBAR_COOKIE}=${state}`,
    `Max-Age=${YEAR_IN_SECONDS}`,
    "Path=/",
    "SameSite=Lax",
    ...(secure ? ["Secure"] : []),
  ].join("; ");
}

interface Target {
  tagName?: string;
  isContentEditable?: boolean;
}

/** True when keys are going into a text box, so a shortcut must stay out of the way. */
export function isEditableTarget(target: Target | null | undefined): boolean {
  if (!target) return false;
  if (target.isContentEditable) return true;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName ?? "");
}

interface KeyLike {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  repeat: boolean;
  target: Target | EventTarget | null;
}

/** `[` on its own collapses or expands the sidebar. */
export function wantsToggle(event: KeyLike): boolean {
  if (event.key !== "[" || event.ctrlKey || event.metaKey || event.altKey || event.repeat)
    return false;
  return !isEditableTarget(event.target as Target | null);
}
