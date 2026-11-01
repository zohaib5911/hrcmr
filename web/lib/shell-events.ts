/**
 * Messages the shell's controls send to features that arrive in later tasks. The toolbar's search box
 * and the help button announce "open the command palette" and "open the keyboard shortcuts"; T1.4
 * builds those and listens. Until then they are announced to nobody, which is harmless.
 */

export const OPEN_PALETTE = "app:open-palette";
export const OPEN_SHORTCUTS = "app:open-shortcuts";

export function announce(
  name: typeof OPEN_PALETTE | typeof OPEN_SHORTCUTS,
  target: Pick<Window, "dispatchEvent"> = window,
): void {
  target.dispatchEvent(new CustomEvent(name));
}
