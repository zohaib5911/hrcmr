import { describe, expect, it } from "vitest";

import {
  GO_TARGETS,
  SEQUENCE_WINDOW_MS,
  SHORTCUT_GROUPS,
  interpretKey,
  type KeyInput,
  type SequenceState,
} from "./shortcuts";

const NONE: SequenceState = { goAt: null };
const key = (k: string, extra: Partial<KeyInput> = {}): KeyInput => ({
  key: k,
  ctrlKey: false,
  metaKey: false,
  altKey: false,
  shiftKey: false,
  repeat: false,
  target: null,
  ...extra,
});
const field = { tagName: "INPUT", isContentEditable: false };

describe("single keys", () => {
  it.each([
    ["?", { type: "shortcuts" }],
    ["[", { type: "toggle-sidebar" }],
    ["/", { type: "focus-search" }],
    ["n", { type: "new" }],
  ])("%s does its job", (k, action) => {
    const result = interpretKey(key(k, { shiftKey: k === "?" }), NONE, 0);
    expect(result.action).toEqual(action);
    expect(result.handled).toBe(true);
  });

  it("is not case sensitive, so Caps Lock does not break shortcuts", () => {
    expect(interpretKey(key("N"), NONE, 0).action).toEqual({ type: "new" });
  });

  it("leaves every other key alone", () => {
    // J, K, Enter, Space and "." belong to a focused table, which handles them itself.
    for (const k of ["a", "Enter", "Escape", "Tab", "ArrowDown", "j", "k", "x", "1", ".", " "]) {
      const result = interpretKey(key(k), NONE, 0);
      expect(result.action, k).toBeNull();
      expect(result.handled, k).toBe(false);
    }
  });
});

describe("the search shortcut (Cmd K / Ctrl K)", () => {
  it("opens the palette with either modifier", () => {
    expect(interpretKey(key("k", { metaKey: true }), NONE, 0).action).toEqual({ type: "palette" });
    expect(interpretKey(key("K", { ctrlKey: true }), NONE, 0).action).toEqual({ type: "palette" });
  });

  it("works even while typing in a field, as every app's search shortcut does", () => {
    const result = interpretKey(key("k", { metaKey: true, target: field }), NONE, 0);
    expect(result.action).toEqual({ type: "palette" });
    expect(result.handled).toBe(true);
  });

  it("does not take Cmd+Shift+K or Alt+K, which belong to the browser", () => {
    expect(interpretKey(key("k", { metaKey: true, shiftKey: true }), NONE, 0).action).toBeNull();
    expect(interpretKey(key("k", { metaKey: true, altKey: true }), NONE, 0).action).toBeNull();
  });
});

describe("while the person is typing", () => {
  it("does nothing, so a / or an n in a text box is just a character", () => {
    for (const target of [
      { tagName: "INPUT" },
      { tagName: "TEXTAREA" },
      { tagName: "SELECT" },
      { tagName: "DIV", isContentEditable: true },
    ]) {
      for (const k of ["?", "[", "/", "n", "g"]) {
        const result = interpretKey(key(k, { target }), NONE, 0);
        expect(result.action, `${target.tagName} ${k}`).toBeNull();
        expect(result.handled, `${target.tagName} ${k}`).toBe(false);
      }
    }
  });

  it("forgets a G that was pressed before focus moved into a field", () => {
    const started = interpretKey(key("g"), NONE, 0);
    const typed = interpretKey(key("d", { target: field }), started.state, 100);
    expect(typed.action).toBeNull();
    expect(typed.state).toEqual({ goAt: null });
  });
});

describe("with a modifier held", () => {
  it("ignores plain shortcuts, so Ctrl+N and Cmd+/ stay with the browser", () => {
    for (const mods of [{ ctrlKey: true }, { metaKey: true }, { altKey: true }]) {
      for (const k of ["n", "/", "[", "g"]) {
        expect(
          interpretKey(key(k, mods), NONE, 0).action,
          `${JSON.stringify(mods)} ${k}`,
        ).toBeNull();
      }
    }
  });

  it("ignores a held-down key (auto-repeat)", () => {
    expect(interpretKey(key("n", { repeat: true }), NONE, 0).handled).toBe(false);
  });
});

describe("G then a letter goes to a page (plan 8.19)", () => {
  it("lists the seven destinations from the plan", () => {
    expect(Object.entries(GO_TARGETS).map(([letter, t]) => `${letter}:${t.label}`)).toEqual([
      "d:Dashboard",
      "e:Employees",
      "r:Recruitment",
      "c:Compliance",
      "l:Leave",
      "a:Attendance",
      "t:Rota",
    ]);
  });

  it.each(Object.entries(GO_TARGETS))("G then %s opens its page", (letter, target) => {
    const first = interpretKey(key("g"), NONE, 1000);
    expect(first.action).toBeNull();
    expect(first.handled).toBe(true);
    expect(first.state).toEqual({ goAt: 1000 });
    const second = interpretKey(key(letter), first.state, 1400);
    expect(second.action).toEqual({ type: "go", href: target.href });
    expect(second.state).toEqual({ goAt: null });
  });

  it("works with Caps Lock", () => {
    const first = interpretKey(key("G"), NONE, 0);
    expect(interpretKey(key("E"), first.state, 100).action).toEqual({
      type: "go",
      href: GO_TARGETS.e?.href,
    });
  });

  it("gives up if the second key comes too late", () => {
    const first = interpretKey(key("g"), NONE, 0);
    const late = interpretKey(key("e"), first.state, SEQUENCE_WINDOW_MS + 1);
    expect(late.action).toBeNull();
    expect(late.state).toEqual({ goAt: null });
  });

  it("gives up on a letter that goes nowhere, and does not run it as a shortcut either", () => {
    const first = interpretKey(key("g"), NONE, 0);
    const wrong = interpretKey(key("z"), first.state, 100);
    expect(wrong.action).toBeNull();
    expect(wrong.state).toEqual({ goAt: null });
    const first2 = interpretKey(key("g"), NONE, 0);
    expect(interpretKey(key("n"), first2.state, 100).action).toBeNull();
  });

  it("G G starts over rather than going anywhere", () => {
    const first = interpretKey(key("g"), NONE, 0);
    const again = interpretKey(key("g"), first.state, 100);
    expect(again.action).toBeNull();
    expect(again.state).toEqual({ goAt: 100 });
  });

  it("is cancelled by pressing a modifier combination in between", () => {
    const first = interpretKey(key("g"), NONE, 0);
    expect(interpretKey(key("e", { ctrlKey: true }), first.state, 100).action).toBeNull();
  });
});

describe("the list shown in the sheet", () => {
  const all = SHORTCUT_GROUPS.flatMap((group) => group.shortcuts);

  it("has a group each for general, going places and lists", () => {
    expect(SHORTCUT_GROUPS.map((g) => g.title)).toEqual([
      "General",
      "Go to a page",
      "Lists and tables",
    ]);
  });

  it("describes every shortcut in the plan table (8.19), with its keys", () => {
    const labels = all.map((s) => s.label);
    for (const wanted of [
      "Search",
      "Show keyboard shortcuts",
      "Collapse or expand the sidebar",
      "Close the top layer",
      "New",
      "Focus the list search",
      "Move down a row",
      "Move up a row",
      "Open the row",
      "Open the row menu",
    ]) {
      expect(labels, wanted).toContain(wanted);
    }
    expect(all.filter((s) => s.keys[0] === "G")).toHaveLength(7);
  });

  it("lists each key combination once", () => {
    const seen = all.map((s) => s.keys.join(" "));
    expect(new Set(seen).size).toBe(seen.length);
  });

  it("every plain-key shortcut that is handled is also listed", () => {
    const listed = new Set(all.map((s) => s.keys.join(" ").toLowerCase()));
    for (const k of ["?", "[", "/", "n"]) expect(listed.has(k), k).toBe(true);
  });
});
