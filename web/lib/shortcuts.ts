/**
 * Keyboard shortcuts (plan 8.19), as pure logic: given a key press and what came before it, what
 * should happen? The browser wiring (listening, navigating, opening the palette) is in
 * components/app/shortcut-provider.tsx, and this is what it asks.
 *
 * Only the shortcuts that work anywhere on the page are here. J, K, Enter, Space and "." act on the
 * highlighted row of a table, so the table handles them itself while it has focus.
 *
 * Rules that keep shortcuts from getting in the way:
 *  - nothing fires while the person is typing in a field (a "/" or an "n" is just a character),
 *    except Cmd/Ctrl+K, which every app lets you press anywhere;
 *  - nothing fires with Ctrl, Cmd or Alt held, so the browser's own shortcuts are left alone;
 *  - a held-down key does not repeat an action.
 */
import { isEditableTarget } from "./sidebar";

/** How long after G the next letter still counts. */
export const SEQUENCE_WINDOW_MS = 1500;

/** "G then ..." destinations (plan 8.19). */
export const GO_TARGETS: Readonly<Record<string, { label: string; href: string }>> = {
  d: { label: "Dashboard", href: "/dashboard" },
  e: { label: "Employees", href: "/employees" },
  r: { label: "Recruitment", href: "/recruitment" },
  c: { label: "Compliance", href: "/sponsor-compliance" },
  l: { label: "Leave", href: "/leave" },
  a: { label: "Attendance", href: "/attendance" },
  t: { label: "Rota", href: "/rota" },
};

export type ShortcutAction =
  | { type: "palette" }
  | { type: "shortcuts" }
  | { type: "toggle-sidebar" }
  | { type: "focus-search" }
  | { type: "new" }
  | { type: "go"; href: string };

export interface KeyInput {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
  repeat: boolean;
  target: { tagName?: string; isContentEditable?: boolean } | EventTarget | null;
}

/** Whether a "G" is waiting for its letter, and when it was pressed. */
export interface SequenceState {
  goAt: number | null;
}

export interface KeyResult {
  action: ShortcutAction | null;
  /** True when the key was ours, so the caller should stop the browser acting on it too. */
  handled: boolean;
  state: SequenceState;
}

const CLEARED: SequenceState = { goAt: null };

export function interpretKey(input: KeyInput, state: SequenceState, now: number): KeyResult {
  if (input.repeat) return { action: null, handled: false, state };
  const key = input.key.toLowerCase();

  if ((input.metaKey || input.ctrlKey) && !input.altKey && !input.shiftKey && key === "k") {
    return { action: { type: "palette" }, handled: true, state: CLEARED };
  }

  const typing = isEditableTarget(
    input.target as { tagName?: string; isContentEditable?: boolean } | null,
  );
  if (input.metaKey || input.ctrlKey || input.altKey || typing) {
    return { action: null, handled: false, state: CLEARED };
  }

  const waiting = state.goAt !== null && now - state.goAt <= SEQUENCE_WINDOW_MS;
  if (waiting) {
    if (key === "g") return { action: null, handled: true, state: { goAt: now } };
    const target = GO_TARGETS[key];
    return target
      ? { action: { type: "go", href: target.href }, handled: true, state: CLEARED }
      : { action: null, handled: false, state: CLEARED };
  }

  switch (key) {
    case "?":
      return { action: { type: "shortcuts" }, handled: true, state: CLEARED };
    case "[":
      return { action: { type: "toggle-sidebar" }, handled: true, state: CLEARED };
    case "/":
      return { action: { type: "focus-search" }, handled: true, state: CLEARED };
    case "n":
      return { action: { type: "new" }, handled: true, state: CLEARED };
    case "g":
      return { action: null, handled: true, state: { goAt: now } };
    default:
      return { action: null, handled: false, state: CLEARED };
  }
}

// ---- What the shortcuts sheet lists (plan 8.19) ----------------------------------------------------

export interface ShortcutInfo {
  /** The keys, in order. "Mod" is Cmd on a Mac and Ctrl elsewhere. */
  keys: readonly string[];
  label: string;
  /** A short note, such as where it works. */
  note?: string;
}

export interface ShortcutGroup {
  title: string;
  shortcuts: readonly ShortcutInfo[];
}

export const SHORTCUT_GROUPS: readonly ShortcutGroup[] = [
  {
    title: "General",
    shortcuts: [
      { keys: ["Mod", "K"], label: "Search" },
      { keys: ["?"], label: "Show keyboard shortcuts" },
      { keys: ["["], label: "Collapse or expand the sidebar" },
      { keys: ["Esc"], label: "Close the top layer", note: "A dialog, sheet, menu or popover." },
      { keys: ["N"], label: "New", note: "On pages where you can add something." },
    ],
  },
  {
    title: "Go to a page",
    shortcuts: Object.entries(GO_TARGETS).map(([letter, target]) => ({
      keys: ["G", letter.toUpperCase()],
      label: `Go to ${target.label}`,
    })),
  },
  {
    title: "Lists and tables",
    shortcuts: [
      { keys: ["/"], label: "Focus the list search" },
      { keys: ["J"], label: "Move down a row" },
      { keys: ["K"], label: "Move up a row" },
      { keys: ["Enter"], label: "Open the row" },
      { keys: ["Space"], label: "Select the row" },
      { keys: ["."], label: "Open the row menu" },
    ],
  },
];
