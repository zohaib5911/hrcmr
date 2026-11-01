/**
 * Behaviour of the components on /design, in a real browser, driven the way people drive them (plan
 * T1.2: "keyboard interaction works for Dialog, Sheet, Menu, Combobox, SegmentedControl, DatePicker
 * and DataTable"). Focus, not just visibility, is what is checked: where it goes, where it is kept
 * and where it returns to.
 */
import { expect, test, type Page } from "@playwright/test";

import { focusedName, focusInside, openDesign, pressArrow } from "../support/design-page";

// Any console error or uncaught exception while using the page fails the test that caused it. (Tests
// in one worker run one after another, so one variable per worker is enough.)
let problems: string[] = [];

test.beforeEach(async ({ page }) => {
  problems = await openDesign(page);
});

test.afterEach(() => {
  expect(problems).toEqual([]);
});

const section = (page: Page, id: string) => page.locator(`#${id}`);

async function focusVisible(page: Page, locator: ReturnType<Page["locator"]>) {
  await locator.scrollIntoViewIfNeeded();
  await locator.focus();
}

test.describe("Dialog", () => {
  test("opens from the keyboard, keeps focus inside, closes with Esc and gives focus back", async ({
    page,
  }) => {
    const trigger = page.getByRole("button", { name: "Open a dialog" });
    await focusVisible(page, trigger);
    await page.keyboard.press("Enter");

    const dialog = page.getByRole("dialog", { name: "Add a location" });
    await expect(dialog).toBeVisible();
    expect(await focusInside(dialog)).toBe(true);

    // More Tab presses than there are controls: focus must wrap inside the dialog, never escape.
    for (let i = 0; i < 9; i += 1) {
      await page.keyboard.press("Tab");
      expect(await focusInside(dialog), `after Tab ${i + 1}`).toBe(true);
    }
    for (let i = 0; i < 9; i += 1) {
      await page.keyboard.press("Shift+Tab");
      expect(await focusInside(dialog), `after Shift+Tab ${i + 1}`).toBe(true);
    }

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test("Cancel closes it and the page behind it is inert while it is open", async ({ page }) => {
    await page.getByRole("button", { name: "Open a dialog" }).click();
    const dialog = page.getByRole("dialog", { name: "Add a location" });
    await expect(dialog).toBeVisible();
    // Behind a modal the rest of the page is hidden from assistive technology.
    await expect(page.getByRole("button", { name: "Open the inspector" })).toHaveCount(0);
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("button", { name: "Open the inspector" })).toHaveCount(1);
  });

  test("on a phone it is a bottom sheet with a grabber", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "Open a dialog" }).click();
    const dialog = page.getByRole("dialog", { name: "Add a location" });
    await expect(dialog).toBeVisible();
    // Its bottom edge is the bottom of the screen, once it has finished sliding up.
    await expect
      .poll(async () => {
        const box = await dialog.boundingBox();
        return Math.round((box?.y ?? 0) + (box?.height ?? 0));
      })
      .toBe(844);
    expect(Math.round((await dialog.boundingBox())?.width ?? 0)).toBe(390);
  });
});

test.describe("Sheet (the inspector)", () => {
  test("opens from the keyboard, traps focus, closes with Esc and gives focus back", async ({
    page,
  }) => {
    const trigger = page.getByRole("button", { name: "Open the inspector" });
    await focusVisible(page, trigger);
    await page.keyboard.press("Space");
    const sheet = page.getByRole("dialog", { name: "Ada Lovelace" });
    await expect(sheet).toBeVisible();
    expect(await focusInside(sheet)).toBe(true);
    for (let i = 0; i < 8; i += 1) {
      await page.keyboard.press("Tab");
      expect(await focusInside(sheet), `after Tab ${i + 1}`).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test("is 440 px wide on the right edge of a desktop screen", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.getByRole("button", { name: "Open the inspector" }).click();
    const sheet = page.getByRole("dialog", { name: "Ada Lovelace" });
    await expect(sheet).toBeVisible();
    // Wait out the slide-in.
    await expect
      .poll(async () => (await sheet.boundingBox())?.x, { timeout: 3000 })
      .toBeCloseTo(1280 - 440, 0);
    expect((await sheet.boundingBox())?.width).toBeCloseTo(440, 0);
  });
});

test.describe("Menu", () => {
  test("opens with Enter, moves with the arrow keys, finds items by typing, and Esc returns focus", async ({
    page,
  }) => {
    const trigger = page.getByRole("button", { name: "Actions", exact: true });
    await focusVisible(page, trigger);
    await page.keyboard.press("Enter");
    const menu = page.getByRole("menu");
    await expect(menu).toBeVisible();

    const highlighted = page.locator(
      '[role^="menuitem"][data-highlighted], [role="menuitemradio"][data-highlighted]',
    );
    await expect(highlighted).toHaveText(/Edit/);
    await page.keyboard.press("ArrowDown");
    await expect(highlighted).toHaveText(/Duplicate/);
    await page.keyboard.press("ArrowDown");
    await expect(highlighted).toHaveText(/Share a link/);

    // Typing a few letters jumps to a matching item.
    await page.keyboard.type("Del");
    await expect(highlighted).toHaveText(/Delete/);

    // Home and End.
    await page.keyboard.press("Home");
    await expect(highlighted).toHaveText(/Edit/);
    await page.keyboard.press("End");
    await expect(highlighted).toHaveText(/Delete/);

    await page.keyboard.press("Escape");
    await expect(menu).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test("a checkbox item toggles with Space and a radio item chooses", async ({ page }) => {
    const trigger = page.getByRole("button", { name: "Actions", exact: true });
    await focusVisible(page, trigger);
    await page.keyboard.press("Enter");
    const checkbox = page.getByRole("menuitemcheckbox", { name: "Show archived" });
    await checkbox.focus();
    await expect(checkbox).toHaveAttribute("aria-checked", "false");
    await page.keyboard.press("Space");
    // It closes after choosing; open it again and see the choice stuck.
    await expect(page.getByRole("menu")).toBeHidden();
    await expect(trigger).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("menu")).toBeVisible();
    await expect(page.getByRole("menuitemcheckbox", { name: "Show archived" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(page.getByRole("menuitemradio", { name: "Name" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  test("a context menu opens with Shift+F10 and closes with Esc", async ({ page }) => {
    const area = page.getByText("Right-click here, or press Shift+F10");
    await focusVisible(page, area);
    await page.keyboard.press("Shift+F10");
    await expect(page.getByRole("menu")).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Download" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menu")).toBeHidden();
  });
});

test.describe("Combobox", () => {
  const field = (page: Page) => section(page, "inputs").locator('input[role="combobox"]').first();

  test("typing filters, arrows move the highlight, Enter chooses, focus never leaves the text box", async ({
    page,
  }) => {
    const input = field(page);
    await input.scrollIntoViewIfNeeded();
    await input.click();
    await expect(input).toHaveAttribute("aria-expanded", "true");
    await input.fill("e"); // matches every department

    const options = page.getByRole("listbox").getByRole("option");
    await expect(options).toHaveCount(5);
    await expect(input).toHaveAttribute("aria-activedescendant", /-option-0$/);

    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowDown");
    await expect(input).toHaveAttribute("aria-activedescendant", /-option-2$/);
    // The highlight moved but focus did not: it is still in the text box.
    await expect(input).toBeFocused();

    await page.keyboard.press("Enter");
    await expect(input).toHaveValue("People");
    await expect(input).toHaveAttribute("aria-expanded", "false");
    await expect(input).toBeFocused();
  });

  test("narrowing the text narrows the list, and Esc closes it without choosing", async ({
    page,
  }) => {
    const input = field(page);
    await input.scrollIntoViewIfNeeded();
    await input.fill("fin");
    await expect(page.getByRole("listbox").getByRole("option")).toHaveCount(1);
    await expect(page.getByRole("listbox").getByRole("option", { name: /Finance/ })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(input).toHaveAttribute("aria-expanded", "false");
    await expect(input).not.toHaveValue("Finance");
  });

  test("says when nothing matches", async ({ page }) => {
    const input = field(page);
    await input.scrollIntoViewIfNeeded();
    await input.fill("zzz");
    await expect(page.getByText("No matches").first()).toBeVisible();
  });

  test("the searching one shows progress, then results, and ignores answers to old searches", async ({
    page,
  }) => {
    const input = section(page, "inputs").locator('input[role="combobox"]').nth(1);
    await input.scrollIntoViewIfNeeded();
    await input.fill("c");
    await expect(page.getByText("Searching…").first()).toBeVisible();
    await expect(
      page.getByRole("listbox").getByRole("option", { name: /Care services/ }),
    ).toBeVisible({
      timeout: 5000,
    });
    // Type more before the first answer would matter: only the latest query's answer is shown.
    await input.fill("fin");
    await expect(page.getByRole("listbox").getByRole("option", { name: /Finance/ })).toBeVisible({
      timeout: 5000,
    });
    await expect(
      page.getByRole("listbox").getByRole("option", { name: /Care services/ }),
    ).toHaveCount(0);
  });
});

test.describe("SegmentedControl", () => {
  test("arrow keys move and choose, wrapping at the ends, and Tab leaves the group", async ({
    page,
  }) => {
    const group = page.getByRole("radiogroup", { name: "Leave view" });
    const calendar = group.getByRole("radio", { name: "Calendar" });
    await focusVisible(page, calendar);
    await expect(calendar).toBeChecked();

    await pressArrow(page, "ArrowRight");
    await expect(group.getByRole("radio", { name: "Requests" })).toBeChecked();
    await expect(group.getByRole("radio", { name: "Requests" })).toBeFocused();
    await pressArrow(page, "ArrowRight");
    await expect(group.getByRole("radio", { name: "Balances" })).toBeChecked();
    await pressArrow(page, "ArrowRight");
    await expect(calendar).toBeChecked(); // wrapped
    await pressArrow(page, "ArrowLeft");
    await expect(group.getByRole("radio", { name: "Balances" })).toBeChecked(); // wrapped back

    await page.keyboard.press("Tab");
    expect(await focusInside(group.locator("xpath=.."))).toBe(false);
  });

  test("is one tab stop, however many segments it has", async ({ page }) => {
    const group = page.getByRole("radiogroup", { name: "Leave view" });
    const stops = await group.evaluate(
      (root) =>
        [root, ...root.querySelectorAll("*")].filter((el) => (el as HTMLElement).tabIndex === 0)
          .length,
    );
    expect(stops).toBe(1);
  });

  test("clicking chooses a segment", async ({ page }) => {
    const group = page.getByRole("radiogroup", { name: "Range" });
    await group.getByRole("radio", { name: "Month" }).click();
    await expect(group.getByRole("radio", { name: "Month" })).toBeChecked();
  });
});

test.describe("DatePicker", () => {
  const startDate = (page: Page) =>
    section(page, "inputs").getByLabel("Start date", { exact: true }).first();

  test("Alt+Down opens the calendar with focus on the date, arrows and paging move it, Enter chooses", async ({
    page,
  }) => {
    const input = startDate(page);
    await focusVisible(page, input);
    await expect(input).toHaveValue("1 Nov 2026");
    await page.keyboard.press("Alt+ArrowDown");

    const calendar = page.getByRole("dialog", { name: "Choose start date" });
    await expect(calendar).toBeVisible();
    await expect(calendar.getByRole("heading", { name: "November 2026" })).toBeVisible();
    await expect.poll(() => focusedName(page)).toMatch(/^Sunday 1 November 2026, .*selected/);

    await page.keyboard.press("ArrowRight");
    await expect.poll(() => focusedName(page)).toMatch(/^Monday 2 November 2026/);
    await page.keyboard.press("ArrowDown");
    await expect.poll(() => focusedName(page)).toMatch(/^Monday 9 November 2026/);
    await page.keyboard.press("ArrowLeft");
    await expect.poll(() => focusedName(page)).toMatch(/^Sunday 8 November 2026/);

    // Past the end of the month turns the page.
    await page.keyboard.press("PageDown");
    await expect(calendar.getByRole("heading", { name: "December 2026" })).toBeVisible();
    await expect.poll(() => focusedName(page)).toMatch(/^Tuesday 8 December 2026/);
    await page.keyboard.press("Shift+PageUp");
    await expect(calendar.getByRole("heading", { name: "December 2025" })).toBeVisible();

    await page.keyboard.press("Home");
    await expect.poll(() => focusedName(page)).toMatch(/^Monday 8 December 2025/);
    await page.keyboard.press("End");
    await expect.poll(() => focusedName(page)).toMatch(/^Sunday 14 December 2025/);

    await page.keyboard.press("Enter");
    await expect(calendar).toBeHidden();
    await expect(input).toHaveValue("14 Dec 2025");
    // Focus returns to the text box, where the person was typing.
    await expect(input).toBeFocused();
  });

  test("Esc closes the calendar without changing the date and returns focus to the text box", async ({
    page,
  }) => {
    const input = startDate(page);
    await focusVisible(page, input);
    await page.keyboard.press("Alt+ArrowDown");
    const calendar = page.getByRole("dialog", { name: "Choose start date" });
    await expect(calendar).toBeVisible();
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("Escape");
    await expect(calendar).toBeHidden();
    await expect(input).toHaveValue("1 Nov 2026");
    await expect(input).toBeFocused();
  });

  test("only one day is a tab stop, and the dots are described", async ({ page }) => {
    const input = startDate(page);
    await focusVisible(page, input);
    await page.keyboard.press("Alt+ArrowDown");
    const calendar = page.getByRole("dialog", { name: "Choose start date" });
    await expect(calendar).toBeVisible();
    const stops = await calendar
      .locator("button[data-iso]")
      .evaluateAll((days) => days.filter((d) => (d as HTMLElement).tabIndex === 0).length);
    expect(stops).toBe(1);
    // A leave marker is part of the day's name, not only a dot.
    await expect(
      calendar.getByRole("button", { name: /Thursday 5 November 2026.*Leave: Ada Lovelace/ }),
    ).toBeVisible();
  });

  test("typing a date in any common form is understood when you leave the field", async ({
    page,
  }) => {
    const input = startDate(page);
    await input.scrollIntoViewIfNeeded();
    await input.fill("5/11/26");
    await input.blur();
    await expect(input).toHaveValue("5 Nov 2026");
    await input.fill("12 december 2026");
    await input.press("Enter");
    await expect(input).toHaveValue("12 Dec 2026");
  });

  test("a date that does not exist is explained, not guessed", async ({ page }) => {
    const input = startDate(page);
    await input.scrollIntoViewIfNeeded();
    await input.fill("31 Feb 2026");
    await input.blur();
    await expect(page.getByText("Enter a date like 1 Nov 2026").first()).toBeVisible();
    await expect(input).toHaveAttribute("aria-invalid", "true");
  });

  test("a date outside the allowed range says what is allowed", async ({ page }) => {
    const input = section(page, "inputs").getByLabel("Date of birth", { exact: true });
    await input.scrollIntoViewIfNeeded();
    await input.fill("2 Nov 2026");
    await input.blur();
    await expect(page.getByText("Choose a date from 1 Jan 1950 to 1 Nov 2026")).toBeVisible();
  });

  test("a range is chosen with two clicks and cannot end before it starts", async ({ page }) => {
    const group = page.getByRole("group", { name: "Leave dates" });
    await group.scrollIntoViewIfNeeded();
    await group.getByRole("button", { name: /Choose leave dates/ }).click();
    const calendar = page.getByRole("dialog", { name: "Choose leave dates" });
    await expect(calendar).toBeVisible();
    await calendar.getByRole("button", { name: /Wednesday 11 November 2026/ }).click();
    await expect(calendar.getByText("Now choose the last day.")).toBeVisible();
    // Choosing an earlier day swaps the two ends.
    await calendar.getByRole("button", { name: /Monday 9 November 2026/ }).click();
    await expect(calendar).toBeHidden();
    await expect(group.getByLabel("Start date", { exact: true })).toHaveValue("9 Nov 2026");
    await expect(group.getByLabel("End date", { exact: true })).toHaveValue("11 Nov 2026");
  });
});

test.describe("DataTable", () => {
  const people = (page: Page) =>
    section(page, "data").getByRole("grid", { name: "Employees", exact: true });
  const activeRow = (page: Page) => people(page).locator("tr[data-active]");

  test("J and K (and the arrows) move through rows, Enter opens, Space selects", async ({
    page,
  }) => {
    const table = people(page);
    await focusVisible(page, table);
    // Focusing the table highlights the first row.
    await expect(activeRow(page)).toContainText("Ada Lovelace");

    await page.keyboard.press("j");
    await expect(activeRow(page)).toContainText("Alan Turing");
    await page.keyboard.press("j");
    await expect(activeRow(page)).toContainText("Barbara Hopper");
    await page.keyboard.press("k");
    await expect(activeRow(page)).toContainText("Alan Turing");
    await page.keyboard.press("ArrowDown");
    await expect(activeRow(page)).toContainText("Barbara Hopper");
    await page.keyboard.press("ArrowUp");
    await expect(activeRow(page)).toContainText("Alan Turing");
    // The highlighted row is exposed to assistive technology.
    const activeId = await activeRow(page).getAttribute("id");
    await expect(table).toHaveAttribute("aria-activedescendant", activeId ?? "");

    await page.keyboard.press("End");
    await expect(activeRow(page)).toContainText("Edsger Dijkstra");
    await page.keyboard.press("Home");
    await expect(activeRow(page)).toContainText("Ada Lovelace");

    await page.keyboard.press("Enter");
    await expect(page.getByText("Opened Ada Lovelace").first()).toBeVisible();

    await page.keyboard.press("Space");
    await expect(section(page, "data").getByText("1 selected")).toBeVisible();
    await expect(table.getByRole("checkbox", { name: "Select Ada Lovelace" })).toBeChecked();
    await page.keyboard.press("Space");
    await expect(section(page, "data").getByText("1 selected")).toBeHidden();
  });

  test("moving past the last row on a page stays on it, and keys do nothing when a button inside has focus", async ({
    page,
  }) => {
    const table = people(page);
    await focusVisible(page, table);
    for (let i = 0; i < 9; i += 1) await page.keyboard.press("j");
    await expect(activeRow(page)).toContainText("Edsger Dijkstra"); // the fifth and last row of page one
    // A focused checkbox keeps its own keys: "j" there must not move the highlight.
    await table.getByRole("checkbox", { name: "Select all rows on this page" }).focus();
    await page.keyboard.press("j");
    await expect(activeRow(page)).toContainText("Edsger Dijkstra");
  });

  test("sorting: a header cycles ascending, descending, off; and says so to screen readers", async ({
    page,
  }) => {
    const table = people(page);
    const header = table.getByRole("columnheader", { name: /Department/ });
    await header.scrollIntoViewIfNeeded();
    await expect(header).toHaveAttribute("aria-sort", "none");
    await header.getByRole("button").click();
    await expect(header).toHaveAttribute("aria-sort", "ascending");
    await expect(table.locator("tbody tr").first()).toContainText("Care"); // Care sorts first
    await header.getByRole("button").focus();
    await page.keyboard.press("Enter");
    await expect(header).toHaveAttribute("aria-sort", "descending");
    await page.keyboard.press("Space");
    await expect(header).toHaveAttribute("aria-sort", "none");
  });

  test("selecting all on the page, and the count", async ({ page }) => {
    const data = section(page, "data");
    const table = people(page);
    await table.scrollIntoViewIfNeeded();
    await table.getByRole("checkbox", { name: "Select all rows on this page" }).click();
    await expect(data.getByText("5 selected")).toBeVisible();
    await table.getByRole("checkbox", { name: "Select Ada Lovelace" }).click();
    await expect(data.getByText("4 selected")).toBeVisible();
    await expect(
      table.getByRole("checkbox", { name: "Select all rows on this page" }),
    ).toHaveAttribute("aria-checked", "mixed");
    await data.getByRole("button", { name: "Clear" }).first().click();
    await expect(data.getByText("4 selected")).toBeHidden();
  });

  test("paging, column visibility, density and export", async ({ page }) => {
    const data = section(page, "data");
    const table = people(page);
    await table.scrollIntoViewIfNeeded();

    await expect(data.getByText("1–5 of 12")).toBeVisible();
    await data.getByRole("button", { name: "Next page" }).first().click();
    await expect(data.getByText("6–10 of 12")).toBeVisible();
    await expect(data.getByRole("button", { name: "Previous page" }).first()).toBeEnabled();

    // A hidden column can be shown again. The menu stays open while choosing.
    await expect(table.getByRole("columnheader", { name: /^Role/ })).toHaveCount(0);
    await data.getByRole("button", { name: "Columns" }).first().click();
    await page.getByRole("menuitemcheckbox", { name: "Role" }).click();
    await expect(page.getByRole("menu")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(table.getByRole("columnheader", { name: /Role/ })).toBeVisible();

    // Density changes the row height.
    const rowHeight = async () =>
      (await table.locator("tbody tr").first().boundingBox())?.height ?? 0;
    const comfortable = await rowHeight();
    await data.getByRole("radio", { name: "Compact" }).first().click();
    await expect.poll(rowHeight).toBeLessThan(comfortable - 8);

    await data.getByRole("button", { name: "Export" }).click();
    await expect(page.getByText("Export ready").first()).toBeVisible();
  });

  test("over 200 rows it draws only the rows in view and still reaches the last one", async ({
    page,
  }) => {
    const big = section(page, "data").getByRole("grid", { name: "All employees" });
    await big.scrollIntoViewIfNeeded();
    await expect(big).toHaveAttribute("aria-rowcount", "1000");
    const drawn = await big.locator("tbody tr:not([aria-hidden])").count();
    expect(drawn).toBeGreaterThan(5);
    expect(drawn).toBeLessThan(80);

    await focusVisible(page, big);
    await page.keyboard.press("End");
    await expect(big.locator('tr[aria-rowindex="1000"]')).toBeAttached();
    await expect(big.locator("tr[data-active]")).toHaveAttribute("aria-rowindex", "1000");
    // Still only a window of rows in the page.
    expect(await big.locator("tbody tr:not([aria-hidden])").count()).toBeLessThan(80);
  });

  test("on a phone each row is a card, with the same data, and pages", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const cards = section(page, "data").getByRole("list", { name: "Employees", exact: true });
    await cards.scrollIntoViewIfNeeded();
    await expect(cards.getByRole("listitem")).toHaveCount(5);
    await expect(
      section(page, "data").getByRole("grid", { name: "Employees", exact: true }),
    ).toHaveCount(0);
    await expect(cards.getByRole("listitem").first()).toContainText("Ada Lovelace");
    await expect(cards.getByRole("listitem").first().getByText("Right to Work")).toBeVisible();
    await cards.getByRole("button", { name: /Open Ada Lovelace/ }).click();
    await expect(page.getByText("Opened Ada Lovelace").first()).toBeVisible();
    // The 1,000-row table pages on a phone instead of drawing a thousand cards.
    const big = section(page, "data").getByRole("list", { name: "All employees" });
    await expect(big.getByRole("listitem")).toHaveCount(25);
  });

  test("an empty table shows its empty state, and a loading one shows placeholders", async ({
    page,
  }) => {
    const data = section(page, "data");
    await expect(data.getByRole("heading", { name: "No employees match" })).toBeVisible();
    await data.getByRole("button", { name: "Show loading" }).click();
    await expect(data.getByRole("status").filter({ hasText: "Loading" }).first()).toBeVisible();
    await data.getByRole("button", { name: "Show the rows" }).click();
    await expect(data.getByRole("grid", { name: "Employees (loading)" })).toBeVisible();
  });
});

test.describe("other controls", () => {
  test("a text field's label floats on focus, and the clear button empties it and keeps focus", async ({
    page,
  }) => {
    const input = section(page, "inputs").getByLabel("Full name", { exact: true }).nth(1); // the filled one
    await input.scrollIntoViewIfNeeded();
    await expect(input).toHaveValue("Ada Lovelace");
    const label = section(page, "inputs").locator(
      'label[for="' + (await input.getAttribute("id")) + '"]',
    );
    expect(await label.evaluate((el) => getComputedStyle(el).fontSize)).toBe("11px");

    await section(page, "inputs").getByRole("button", { name: "Clear Full name" }).nth(0).click();
    await expect(input).toHaveValue("");
    await expect(input).toBeFocused();
    await input.blur();
    await expect.poll(() => label.evaluate((el) => getComputedStyle(el).fontSize)).toBe("15px");
  });

  test("a text area grows with its text, up to a limit", async ({ page }) => {
    const area = section(page, "inputs").getByLabel("Notes", { exact: true });
    await area.scrollIntoViewIfNeeded();
    const before = (await area.boundingBox())?.height ?? 0;
    await area.fill(Array.from({ length: 30 }, (_, i) => `line ${i + 1}`).join("\n"));
    const after = (await area.boundingBox())?.height ?? 0;
    expect(after).toBeGreaterThan(before + 40);
    expect(after).toBeLessThanOrEqual(321); // max-h-80
  });

  test("a money field tidies what you type, and the arrow keys step it", async ({ page }) => {
    const salary = page.getByRole("spinbutton", { name: "Salary" });
    await salary.scrollIntoViewIfNeeded();
    await salary.fill("£52,000.5");
    await salary.blur();
    await expect(salary).toHaveValue("52,000.50");
    await salary.focus();
    await page.keyboard.press("ArrowUp");
    await expect(salary).toHaveValue("52,001.50");
    await salary.fill("abc");
    await salary.blur();
    await expect(page.getByText("Enter a number, for example 1,250.50")).toBeVisible();
  });

  test("a time field reads loose entries and the arrow keys step by 15 minutes", async ({
    page,
  }) => {
    const time = section(page, "inputs").getByLabel("Shift starts", { exact: true });
    await time.scrollIntoViewIfNeeded();
    await time.fill("5pm");
    await time.blur();
    await expect(time).toHaveValue("17:00");
    await time.focus();
    await page.keyboard.press("ArrowUp");
    await expect(time).toHaveValue("17:15");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowDown");
    await expect(time).toHaveValue("16:45");
  });

  test("a switch toggles from its label and from the keyboard", async ({ page }) => {
    const toggle = page.getByRole("switch", { name: /E-mail me about expiring checks/ });
    await toggle.scrollIntoViewIfNeeded();
    await expect(toggle).toBeChecked();
    await page.getByText("E-mail me about expiring checks").click();
    await expect(toggle).not.toBeChecked();
    await toggle.focus();
    await page.keyboard.press("Space");
    await expect(toggle).toBeChecked();
  });

  test("tabs move with the arrow keys and show their panel", async ({ page }) => {
    const first = page.getByRole("tab", { name: "Overview" });
    await focusVisible(page, first);
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("tab", { name: "Personal" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.getByText("Name, contact details and emergency contacts.")).toBeVisible();
  });

  test("radio cards are one group moved with the arrow keys", async ({ page }) => {
    const group = page.getByRole("radiogroup", { name: "Role" });
    await group.scrollIntoViewIfNeeded();
    await group.getByRole("radio", { name: /Employee/ }).focus();
    await pressArrow(page, "ArrowRight");
    await expect(group.getByRole("radio", { name: /Line manager/ })).toBeChecked();
  });

  test("a deletion asks for the name, starts on Cancel, and Esc leaves nothing done", async ({
    page,
  }) => {
    const trigger = page.getByRole("button", { name: "Delete permanently" });
    await trigger.scrollIntoViewIfNeeded();
    await trigger.click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
    const confirm = dialog.getByRole("button", { name: "Delete forever" });
    await expect(confirm).toBeDisabled();
    await dialog.getByLabel("Type Ada Lovelace to confirm").fill("Ada Lovelac");
    await expect(confirm).toBeDisabled();
    await dialog.getByLabel("Type Ada Lovelace to confirm").fill("Ada Lovelace");
    await expect(confirm).toBeEnabled();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(page.getByText("Deleted", { exact: true })).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test("the inline confirmation asks in place, Esc cancels and focus comes back", async ({
    page,
  }) => {
    const trigger = page.getByRole("button", { name: "Mark as left" });
    await trigger.scrollIntoViewIfNeeded();
    await trigger.click();
    const group = page.getByRole("group", { name: "Mark Ada as left?" });
    await expect(group).toBeVisible();
    await expect(group.getByRole("button", { name: "Mark as left" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(group).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test("a toast offers Undo and can be dismissed", async ({ page }) => {
    const trigger = page.getByRole("button", { name: "Success with Undo" });
    await trigger.scrollIntoViewIfNeeded();
    await trigger.click();
    await expect(page.getByText("Leave approved").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Undo" }).first()).toBeVisible();
    await page.getByRole("button", { name: "Dismiss notification" }).click();
    // The toast itself is gone. (Radix keeps an invisible screen-reader copy of it for a moment.)
    await expect(page.getByRole("button", { name: "Dismiss notification" })).toHaveCount(0);
  });

  test("a tooltip appears on keyboard focus", async ({ page }) => {
    const button = page.getByRole("button", { name: "Hover or focus me" });
    await button.scrollIntoViewIfNeeded();
    await button.focus();
    await expect(page.getByText("Shown on hover and on keyboard focus").first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByText("Shown on hover and on keyboard focus")).toHaveCount(0);
  });

  test("the file drop refuses a type that is not allowed and explains, then accepts a good one and scans it", async ({
    page,
  }) => {
    const input = section(page, "files").locator('input[type="file"]').first();
    await input.setInputFiles({
      name: "run.exe",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("MZ"),
    });
    await expect(section(page, "files").getByRole("alert").first()).toContainText(
      "This file type is not allowed. Use PDF, DOCX or an image.",
    );

    await input.setInputFiles({
      name: "passport.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4"),
    });
    const files = section(page, "files").getByRole("list", { name: "Files" }).first();
    await expect(files.getByText("passport.pdf")).toBeVisible();
    await expect(files.getByText("Scanning…")).toBeVisible({ timeout: 5000 });
    await expect(files.getByText("Safe")).toBeVisible({ timeout: 6000 });

    await input.setInputFiles({
      name: "virus-sample.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4"),
    });
    await expect(files.getByText("Rejected")).toBeVisible({ timeout: 8000 });
  });

  test("skeletons stand still when motion is reduced", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const skeleton = section(page, "feedback").locator(".skeleton").first();
    await skeleton.scrollIntoViewIfNeeded();
    expect(await skeleton.evaluate((el) => getComputedStyle(el, "::after").animationName)).toBe(
      "none",
    );
  });

  test("skeletons shimmer by default", async ({ page }) => {
    const skeleton = section(page, "feedback").locator(".skeleton").first();
    await skeleton.scrollIntoViewIfNeeded();
    expect(await skeleton.evaluate((el) => getComputedStyle(el, "::after").animationName)).toBe(
      "skeleton-shimmer",
    );
  });
});
