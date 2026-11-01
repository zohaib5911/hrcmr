import { sidebarCookie, type SidebarState } from "./sidebar";

/** Remembers the sidebar state for the next page load. (The document is passed in so tests can stand in.) */
export function saveSidebarState(
  state: SidebarState,
  target: { cookie: string },
  secure: boolean,
): void {
  target.cookie = sidebarCookie(state, secure);
}
