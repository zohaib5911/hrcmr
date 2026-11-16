// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NAV_GROUPS, NAV_ITEMS } from "@/lib/navigation";
import { OPEN_PALETTE, OPEN_SHORTCUTS } from "@/lib/shell-events";

import { mockNext, router } from "../../tests/unit/support/next-mocks";
import type { ShellSession } from "./shell-types";

const SESSION: ShellSession = {
  user: { name: "Ada Lovelace", email: "ada@example.test", role: "Company Admin" },
  company: { id: "c1", name: "Analytical Engines Ltd", plan: "annual" },
  companies: [{ id: "c1", name: "Analytical Engines Ltd", plan: "annual" }],
};

async function loadShell(pathname: string) {
  vi.resetModules();
  mockNext(pathname);
  const { AppShell } = await import("./app-shell");
  return AppShell;
}

function cookieValue(name: string) {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${name}=`))
    ?.split("=")[1];
}

beforeEach(() => {
  document.cookie = "sidebar=; Max-Age=0; Path=/";
  document.cookie = "theme=; Max-Age=0; Path=/";
  router.push.mockClear();
});
afterEach(() => vi.doUnmock("next/navigation"));

describe("the sidebar", () => {
  it("lists every group and item from the navigation, in order, under small-caps captions", async () => {
    const AppShell = await loadShell("/employees");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(
      within(nav)
        .getAllByRole("heading", { level: 2 })
        .map((h) => h.textContent),
    ).toEqual(NAV_GROUPS.map((g) => g.label));
    expect(
      within(nav)
        .getAllByRole("link")
        .map((l) => l.textContent),
    ).toEqual(NAV_ITEMS.map((i) => i.label));
  });

  it("marks only the current page, and a child page does not light up its parent", async () => {
    const AppShell = await loadShell("/sponsor-compliance/reminders");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    const nav = screen.getByRole("navigation", { name: "Main" });
    const current = within(nav)
      .getAllByRole("link")
      .filter((l) => l.getAttribute("aria-current") === "page");
    expect(current.map((l) => l.textContent)).toEqual(["Reminders"]);
  });

  it("shows the company and the person once the session is there", async () => {
    const AppShell = await loadShell("/employees");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    expect(screen.getByText("Analytical Engines Ltd")).toBeInTheDocument();
    expect(screen.getByText("1 year")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ada Lovelace/ })).toHaveAttribute("href", "/profile");
  });

  it("shows loading placeholders, not made-up names, while there is no session", async () => {
    const AppShell = await loadShell("/employees");
    render(
      <AppShell initialCollapsed={false} theme="system" session={null}>
        page
      </AppShell>,
    );
    expect(screen.getAllByRole("status").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("Analytical Engines Ltd")).not.toBeInTheDocument();
  });

  it("shows a count where there is something to count, and says it aloud", async () => {
    const AppShell = await loadShell("/employees");
    render(
      <AppShell
        initialCollapsed={false}
        theme="system"
        session={SESSION}
        badges={{ reminders: 3, leave: 12 }}
      >
        page
      </AppShell>,
    );
    const reminders = within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", {
      name: /Reminders/,
    });
    expect(reminders).toHaveAccessibleName(/^Reminders.*3 waiting$/);
    expect(
      within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", {
        name: "Employees",
      }),
    ).toBeInTheDocument();
  });
});

describe("collapsing the sidebar", () => {
  it("starts as the cookie said, so the first paint is the right width", async () => {
    const AppShell = await loadShell("/employees");
    const { container } = render(
      <AppShell initialCollapsed theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    expect(container.querySelector("[data-collapsed]")).toHaveAttribute("data-collapsed", "true");
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("the button toggles it, remembers it, and says what it will do", async () => {
    const AppShell = await loadShell("/employees");
    const { container } = render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(container.querySelector("[data-collapsed]")).toHaveAttribute("data-collapsed", "true");
    expect(cookieValue("sidebar")).toBe("collapsed");
    await userEvent.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(container.querySelector("[data-collapsed]")).toHaveAttribute("data-collapsed", "false");
    expect(cookieValue("sidebar")).toBe("expanded");
  });

  it("the [ key toggles it (plan 8.19)", async () => {
    const AppShell = await loadShell("/employees");
    const { container } = render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    await userEvent.keyboard("[["); // user-event writes a literal [ as [[
    expect(container.querySelector("[data-collapsed]")).toHaveAttribute("data-collapsed", "true");
    await userEvent.keyboard("[[");
    expect(container.querySelector("[data-collapsed]")).toHaveAttribute("data-collapsed", "false");
  });

  it("the [ key does nothing while typing, or with a modifier", async () => {
    const AppShell = await loadShell("/employees");
    const { container } = render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        <label>
          Notes <input />
        </label>
      </AppShell>,
    );
    await userEvent.type(screen.getByLabelText("Notes"), "[[[["); // two [ characters
    expect(container.querySelector("[data-collapsed]")).toHaveAttribute("data-collapsed", "false");
    expect(screen.getByLabelText("Notes")).toHaveValue("[[");
    await userEvent.click(document.body);
    await userEvent.keyboard("{Control>}[[{/Control}");
    expect(container.querySelector("[data-collapsed]")).toHaveAttribute("data-collapsed", "false");
  });

  it("keeps every label available to screen readers when collapsed", async () => {
    const AppShell = await loadShell("/employees");
    render(
      <AppShell initialCollapsed theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Employees" })).toBeInTheDocument();
    expect(within(nav).getAllByRole("link")).toHaveLength(NAV_ITEMS.length);
  });
});

describe("the page frame", () => {
  it("starts with a skip link to the main content, and the page is in a focusable main", async () => {
    const AppShell = await loadShell("/employees");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page text
      </AppShell>,
    );
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
    const main = screen.getByRole("main");
    expect(main).toHaveAttribute("id", "main");
    expect(main).toHaveAttribute("tabindex", "-1");
    expect(main).toHaveTextContent("page text");
  });

  it("the toolbar names the page and its place in the app", async () => {
    const AppShell = await loadShell("/sponsor-compliance/migrant-employees");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    const crumbs = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(
      within(crumbs)
        .getAllByRole("listitem")
        .map((li) => li.textContent?.replace("/", "")),
    ).toEqual(["Compliance", "Sponsor compliance", "Sponsored employees"]);
    expect(within(crumbs).getByText("Sponsored employees")).toHaveAttribute("aria-current", "page");
    expect(within(crumbs).getByRole("link", { name: "Sponsor compliance" })).toHaveAttribute(
      "href",
      "/sponsor-compliance",
    );
  });
});

describe("the toolbar's controls", () => {
  it("search and help announce what they want to open; the shortcut provider answers", async () => {
    const AppShell = await loadShell("/employees");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    const heard: string[] = [];
    window.addEventListener(OPEN_PALETTE, () => heard.push("palette"));
    window.addEventListener(OPEN_SHORTCUTS, () => heard.push("shortcuts"));
    // There are two: the wide search box and the phone icon. Either opens the palette.
    for (const button of screen.getAllByRole("button", { name: /^Search/ })) {
      await userEvent.click(button);
      expect(await screen.findByRole("dialog", { name: "Search" })).toBeVisible();
      await userEvent.keyboard("{Escape}");
    }
    await userEvent.click(screen.getByRole("button", { name: "Help and keyboard shortcuts" }));
    expect(await screen.findByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
    expect(heard).toEqual(["palette", "palette", "shortcuts"]);
  });

  it("the bell opens a calm empty state when there is nothing new", async () => {
    const AppShell = await loadShell("/employees");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect(await screen.findByText("You're all caught up")).toBeInTheDocument();
  });

  it("the bell shows how many are unread, in its name", async () => {
    const AppShell = await loadShell("/employees");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION} notificationCount={4}>
        page
      </AppShell>,
    );
    expect(
      screen.getByRole("button", { name: "Notifications, 4 total, 4 unread" }),
    ).toBeInTheDocument();
  });

  it("the account menu shows who you are, goes to your profile, and changes the theme", async () => {
    const AppShell = await loadShell("/employees");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Account menu" }));
    expect(await screen.findByText("ada@example.test")).toBeInTheDocument();
    expect(screen.getByRole("menuitemradio", { name: /System/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await userEvent.click(screen.getByRole("menuitemradio", { name: /Dark/ }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(cookieValue("theme")).toBe("dark");
    document.documentElement.removeAttribute("data-theme");

    await userEvent.click(screen.getByRole("button", { name: "Account menu" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "My profile" }));
    expect(router.push).toHaveBeenCalledWith("/profile");
  });
});

describe("the phone tab bar", () => {
  it("has Home, People, Compliance, Time, Me and More, and marks the section you are in", async () => {
    const AppShell = await loadShell("/leave");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    const bar = screen.getByRole("navigation", { name: "Primary" });
    expect(
      within(bar)
        .getAllByRole("link")
        .map((l) => l.textContent),
    ).toEqual(["Home", "People", "Compliance", "Time", "Me"]);
    expect(within(bar).getByRole("button", { name: "More" })).toBeInTheDocument();
    expect(within(bar).getByRole("link", { name: "Time" })).toHaveAttribute("aria-current", "true");
    expect(within(bar).getByRole("link", { name: "People" })).not.toHaveAttribute("aria-current");
  });

  it("More opens a sheet with every page, and choosing one closes it", async () => {
    const AppShell = await loadShell("/recruitment");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    const bar = screen.getByRole("navigation", { name: "Primary" });
    await userEvent.click(within(bar).getByRole("button", { name: "More" }));
    const sheet = await screen.findByRole("dialog", { name: "More" });
    expect(within(sheet).getAllByRole("link")).toHaveLength(NAV_ITEMS.length);
    expect(within(sheet).getByRole("link", { name: "Recruitment" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await userEvent.click(within(sheet).getByRole("link", { name: "Work log" }));
    expect(screen.queryByRole("dialog", { name: "More" })).not.toBeInTheDocument();
  });

  it("lights up More when you are on a page that has no tab of its own", async () => {
    const AppShell = await loadShell("/company/billing");
    render(
      <AppShell initialCollapsed={false} theme="system" session={SESSION}>
        page
      </AppShell>,
    );
    const bar = screen.getByRole("navigation", { name: "Primary" });
    expect(within(bar).getByRole("button", { name: "More" })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });
});
