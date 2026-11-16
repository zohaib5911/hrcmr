// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useCallback, useState, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NAV_ITEMS } from "@/lib/navigation";
import { RECENT_PAGES_KEY } from "@/lib/recent-pages";
import { GO_TARGETS, SHORTCUT_GROUPS } from "@/lib/shortcuts";

import { mockNext, router } from "../../tests/unit/support/next-mocks";

/** What a page can use from the shortcut provider. It is loaded together with the shell, so they share one registry. */
interface Api {
  register: (handler: () => void) => void;
}

async function setup(
  children: ReactNode | ((api: Api) => ReactNode) = "page",
  pathname = "/employees",
) {
  vi.resetModules();
  mockNext(pathname);
  const { AppShell } = await import("./app-shell");
  const { useNewShortcut } = await import("./shortcut-provider");
  const api: Api = { register: useNewShortcut };
  return render(
    <AppShell initialCollapsed={false} theme="system" session={null}>
      {typeof children === "function" ? children(api) : children}
    </AppShell>,
  );
}

beforeEach(() => {
  router.push.mockClear();
  window.localStorage.clear();
  document.cookie = "sidebar=; Max-Age=0; Path=/";
});
afterEach(() => vi.doUnmock("next/navigation"));

const palette = () => screen.getByRole("dialog", { name: "Search" });
const combobox = () => within(palette()).getByRole("combobox", { name: "Search pages" });

describe("opening the command palette", () => {
  it.each([
    ["Ctrl", "{Control>}k{/Control}"],
    ["Cmd", "{Meta>}k{/Meta}"],
  ])("%s K opens it with the cursor in the search box", async (_name, keys) => {
    await setup();
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.keyboard(keys);
    expect(await screen.findByRole("dialog", { name: "Search" })).toBeVisible();
    expect(combobox()).toHaveFocus();
  });

  it("opens even from inside a text box, as the shortcut in every other app does", async () => {
    await setup(
      <label>
        Notes <input />
      </label>,
    );
    await userEvent.click(screen.getByLabelText("Notes"));
    await userEvent.keyboard("{Control>}k{/Control}");
    expect(palette()).toBeVisible();
  });

  it("opens from the toolbar's search button, and from the icon used on a phone", async () => {
    await setup();
    for (const button of screen.getAllByRole("button", { name: /^Search/ })) {
      await userEvent.click(button);
      expect(palette()).toBeVisible();
      await userEvent.keyboard("{Escape}");
      expect(screen.queryByRole("dialog")).toBeNull();
    }
  });

  it("Esc closes it, and Ctrl K again closes it too", async () => {
    await setup();
    await userEvent.keyboard("{Control>}k{/Control}");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.keyboard("{Control>}k{/Control}");
    expect(palette()).toBeVisible();
    await userEvent.keyboard("{Control>}k{/Control}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("starts empty each time it opens", async () => {
    await setup();
    await userEvent.keyboard("{Control>}k{/Control}");
    await userEvent.type(combobox(), "leave");
    await userEvent.keyboard("{Escape}");
    await userEvent.keyboard("{Control>}k{/Control}");
    expect(combobox()).toHaveValue("");
  });
});

describe("searching", () => {
  it("lists every page when nothing is typed, grouped as the sidebar is", async () => {
    await setup();
    await userEvent.keyboard("{Control>}k{/Control}");
    const options = within(palette()).getAllByRole("option");
    expect(options.map((option) => option.textContent)).toEqual(
      expect.arrayContaining(NAV_ITEMS.map((item) => expect.stringContaining(item.label))),
    );
    expect(options).toHaveLength(NAV_ITEMS.length);
  });

  it("narrows as you type, and Enter opens the first match", async () => {
    await setup();
    await userEvent.keyboard("{Control>}k{/Control}");
    await userEvent.type(combobox(), "rota");
    expect(within(palette()).getAllByRole("option")[0]).toHaveTextContent("Rota");
    await userEvent.keyboard("{Enter}");
    expect(router.push).toHaveBeenCalledWith("/rota");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("the arrow keys move the highlight, wrap round, and keep the cursor in the box", async () => {
    await setup();
    await userEvent.keyboard("{Control>}k{/Control}");
    const options = () => within(palette()).getAllByRole("option");
    expect(options()[0]).toHaveAttribute("aria-selected", "true");
    expect(combobox()).toHaveAttribute("aria-activedescendant", options()[0]?.id);

    await userEvent.keyboard("{ArrowDown}");
    expect(options()[1]).toHaveAttribute("aria-selected", "true");
    expect(combobox()).toHaveAttribute("aria-activedescendant", options()[1]?.id);

    await userEvent.keyboard("{ArrowUp}{ArrowUp}");
    expect(options().at(-1)).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{ArrowDown}");
    expect(options()[0]).toHaveAttribute("aria-selected", "true");
    expect(combobox()).toHaveFocus();

    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(router.push).toHaveBeenCalledWith(NAV_ITEMS[1]?.href);
  });

  it("clicking a result opens it", async () => {
    await setup();
    await userEvent.keyboard("{Control>}k{/Control}");
    await userEvent.click(within(palette()).getByRole("option", { name: /Attendance/ }));
    expect(router.push).toHaveBeenCalledWith("/attendance");
  });

  it("says so when nothing matches, and Enter then does nothing", async () => {
    await setup();
    await userEvent.keyboard("{Control>}k{/Control}");
    await userEvent.type(combobox(), "zzzzz");
    expect(within(palette()).getByText(/No pages match/)).toBeVisible();
    expect(within(palette()).queryAllByRole("option")).toHaveLength(0);
    expect(combobox()).not.toHaveAttribute("aria-activedescendant");
    await userEvent.keyboard("{Enter}");
    expect(router.push).not.toHaveBeenCalled();
    expect(palette()).toBeVisible();
  });

  it("is a labelled combobox that announces how many results there are", async () => {
    await setup();
    await userEvent.keyboard("{Control>}k{/Control}");
    expect(combobox()).toHaveAttribute("aria-expanded", "true");
    expect(within(palette()).getByRole("listbox", { name: "Results" })).toBeVisible();
    expect(within(palette()).getByRole("status")).toHaveTextContent(`${NAV_ITEMS.length} results`);
    await userEvent.type(combobox(), "leave");
    expect(within(palette()).getByRole("status")).toHaveTextContent(/^\d+ results?$/);
  });
});

describe("recent pages", () => {
  it("remembers the pages visited, newest first, in localStorage", async () => {
    await setup("page", "/leave");
    expect(JSON.parse(window.localStorage.getItem(RECENT_PAGES_KEY) ?? "null")).toEqual(["/leave"]);
  });

  it("shows them first, above the pages, without the page you are on", async () => {
    window.localStorage.setItem(RECENT_PAGES_KEY, JSON.stringify(["/rota", "/leave"]));
    await setup("page", "/leave");
    await userEvent.keyboard("{Control>}k{/Control}");
    const options = within(palette()).getAllByRole("option");
    expect(options[0]).toHaveTextContent("Rota");
    // "/leave" is the current page, so it is not offered as "recent".
    expect(within(palette()).getAllByText("Recent")).toHaveLength(1);
    expect(options.filter((option) => /Leave/.test(option.textContent ?? ""))).toHaveLength(
      NAV_ITEMS.filter((item) => item.label.includes("Leave")).length,
    );
  });

  it("ignores anything in storage that is not a page of the app", async () => {
    window.localStorage.setItem(
      RECENT_PAGES_KEY,
      JSON.stringify(["javascript:alert(1)", "https://evil.example/", "/rota", 42, null]),
    );
    await setup("page", "/dashboard");
    await userEvent.keyboard("{Control>}k{/Control}");
    const options = within(palette()).getAllByRole("option");
    expect(options.length).toBe(NAV_ITEMS.length + 1); // the Recent copy of Rota, plus every page
    expect(palette().innerHTML).not.toContain("javascript:");
    expect(palette().innerHTML).not.toContain("evil.example");
  });

  it("works without storage (private browsing, or storage switched off)", async () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    try {
      await setup();
      await userEvent.keyboard("{Control>}k{/Control}");
      expect(within(palette()).getAllByRole("option")).toHaveLength(NAV_ITEMS.length);
    } finally {
      getItem.mockRestore();
      setItem.mockRestore();
    }
  });
});

describe("G then a letter goes to a page (plan 8.19)", () => {
  it.each(Object.entries(GO_TARGETS))("G then %s goes to %o", async (letter, target) => {
    await setup();
    await userEvent.keyboard(`g${letter}`);
    expect(router.push).toHaveBeenCalledExactlyOnceWith(target.href);
  });

  it("every destination is a page that exists in the navigation", () => {
    const hrefs = NAV_ITEMS.map((item) => item.href);
    for (const target of Object.values(GO_TARGETS)) expect(hrefs).toContain(target.href);
  });

  it("G then a letter that goes nowhere does nothing", async () => {
    await setup();
    await userEvent.keyboard("gz");
    expect(router.push).not.toHaveBeenCalled();
  });

  it("a letter on its own does nothing", async () => {
    await setup();
    await userEvent.keyboard("delrcat");
    expect(router.push).not.toHaveBeenCalled();
  });
});

describe("the shortcuts sheet", () => {
  it("opens with ?, and from the help button", async () => {
    await setup();
    await userEvent.keyboard("?");
    expect(await screen.findByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Help and keyboard shortcuts" }));
    expect(screen.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
  });

  it("? again closes it", async () => {
    await setup();
    await userEvent.keyboard("?");
    await userEvent.keyboard("?");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("lists every shortcut of the plan, in three groups", async () => {
    await setup();
    await userEvent.keyboard("?");
    const sheet = screen.getByRole("dialog", { name: "Keyboard shortcuts" });
    const headings = within(sheet)
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(headings).toEqual(["General", "Go to a page", "Lists and tables"]);
    for (const group of SHORTCUT_GROUPS)
      for (const shortcut of group.shortcuts)
        expect(within(sheet).getByText(shortcut.label)).toBeVisible();

    // The plan's list (8.19), written out again here so that dropping one from the code fails this test.
    for (const label of [
      "Search",
      "Show keyboard shortcuts",
      "Collapse or expand the sidebar",
      "Close the top layer",
      "New",
      "Go to Dashboard",
      "Go to Employees",
      "Go to Recruitment",
      "Go to Compliance",
      "Go to Leave",
      "Go to Attendance",
      "Go to Rota",
      "Focus the list search",
      "Move down a row",
      "Move up a row",
      "Open the row",
      "Select the row",
      "Open the row menu",
    ])
      expect(within(sheet).getByText(label)).toBeVisible();
  });

  it("writes keys as keys, with 'then' between the two presses of a G shortcut", async () => {
    await setup();
    await userEvent.keyboard("?");
    const sheet = screen.getByRole("dialog", { name: "Keyboard shortcuts" });
    const row = within(sheet).getByText("Go to Employees").closest("li");
    expect(row).not.toBeNull();
    const keys = within(row as HTMLElement).getAllByText(/^[GE]$/);
    expect(keys.map((key) => key.tagName)).toEqual(["KBD", "KBD"]);
    expect(row).toHaveTextContent("then");
  });
});

describe("N (new)", () => {
  function AddPage({ onNew, api }: { onNew: () => void; api: Api }) {
    const handler = useCallback(() => onNew(), [onNew]);
    api.register(handler);
    return <p>Add something here</p>;
  }

  /** A page that can be navigated away from, to show the shortcut goes with it. */
  function Host({ onNew, api }: { onNew: () => void; api: Api }) {
    const [here, setHere] = useState(true);
    return (
      <>
        <button type="button" onClick={() => setHere(false)}>
          Leave this page
        </button>
        {here ? <AddPage onNew={onNew} api={api} /> : <p>Another page</p>}
      </>
    );
  }

  it("does what the page registered", async () => {
    const onNew = vi.fn();
    await setup((api) => <AddPage onNew={onNew} api={api} />);
    await userEvent.keyboard("n");
    expect(onNew).toHaveBeenCalledTimes(1);
    await userEvent.keyboard("N");
    expect(onNew).toHaveBeenCalledTimes(2);
  });

  it("stops when the page is left, and does nothing on a page that registered nothing", async () => {
    const onNew = vi.fn();
    await setup((api) => <Host onNew={onNew} api={api} />);
    await userEvent.click(screen.getByRole("button", { name: "Leave this page" }));
    await userEvent.keyboard("n");
    expect(onNew).not.toHaveBeenCalled();
    expect(router.push).not.toHaveBeenCalled();
  });

  it("does not fire while typing in a field on that page", async () => {
    const onNew = vi.fn();
    await setup((api) => (
      <>
        <AddPage onNew={onNew} api={api} />
        <label>
          Name <input />
        </label>
      </>
    ));
    await userEvent.type(screen.getByLabelText("Name"), "nina");
    expect(onNew).not.toHaveBeenCalled();
  });
});

describe("/ (focus the list search)", () => {
  it("moves the cursor to the page's list search without typing a slash into it", async () => {
    // jsdom does no layout, so it says nothing is visible; a browser lays the box out.
    const layout = vi
      .spyOn(HTMLElement.prototype, "getClientRects")
      .mockReturnValue([{}] as unknown as DOMRectList);
    try {
      await setup(<input data-list-search aria-label="Search people" />);
      await userEvent.keyboard("/");
      expect(screen.getByLabelText("Search people")).toHaveFocus();
      expect(screen.getByLabelText("Search people")).toHaveValue("");
    } finally {
      layout.mockRestore();
    }
  });

  it("skips a list search that is not showing (hidden at this width)", async () => {
    // With no layout at all (jsdom's default) nothing counts as showing.
    await setup(<input data-list-search aria-label="Search people" />);
    const proceeded = fireEvent.keyDown(document.body, { key: "/" });
    expect(proceeded).toBe(true);
    expect(screen.getByLabelText("Search people")).not.toHaveFocus();
  });

  it("leaves the key alone when the page has no list search", async () => {
    await setup();
    const proceeded = fireEvent.keyDown(document.body, { key: "/" });
    expect(proceeded).toBe(true); // not default-prevented, so the browser's own use of "/" still works
  });
});

describe("staying out of the way", () => {
  it("does nothing while typing in a field", async () => {
    await setup(
      <label>
        Notes <input />
      </label>,
    );
    await userEvent.type(screen.getByLabelText("Notes"), "ge?n/[[");
    expect(router.push).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByLabelText("Notes")).toHaveValue("ge?n/[");
  });

  it("does nothing with Ctrl, Cmd or Alt held, so the browser's own shortcuts still work", async () => {
    await setup();
    for (const modifier of ["Control", "Meta", "Alt"])
      await userEvent.keyboard(`{${modifier}>}g{/${modifier}}{${modifier}>}e{/${modifier}}`);
    expect(router.push).not.toHaveBeenCalled();
  });

  it("does nothing while another dialog is open", async () => {
    await setup(
      <>
        <p>Page</p>
        <div role="dialog" data-state="open" aria-label="Add a location">
          <button type="button">Save</button>
        </div>
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await userEvent.keyboard("ge");
    await userEvent.keyboard("?");
    expect(router.push).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog", { name: "Keyboard shortcuts" })).toBeNull();
  });

  it("while the sheet is open, the keys do not move you to another page behind it", async () => {
    await setup();
    await userEvent.keyboard("?");
    await userEvent.keyboard("ge");
    expect(router.push).not.toHaveBeenCalled();
  });
});
