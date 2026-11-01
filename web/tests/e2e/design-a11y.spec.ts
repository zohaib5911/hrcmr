/**
 * Accessibility of every component on /design (plan T1.2: "axe shows 0 serious issues"). It is
 * stricter than that: ZERO violations at any severity, against WCAG 2.2 AA and axe's best practices,
 * in both themes, at desktop and phone width, and with each overlay OPEN (dialogs, menus and the
 * calendar are drawn outside the page, so a scan of the page alone never sees them).
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { openDesign } from "../support/design-page";

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];

/**
 * Some contrast checks axe genuinely cannot make, and reports as "incomplete": text over a
 * translucent material on a gradient, an empty input (no text yet; its floating label is a separate
 * element that IS checked), a one-character unit, and text beside an SVG. Nothing else may be undecided.
 * The colour pairs behind them are checked by tests/unit/design/tokens.test.ts.
 */
const TRANSLUCENT = /material-(chrome|sheet)/;
const UNDECIDABLE = /Element has no value|content is too short|contains an image node/;

/**
 * What is accepted, and why. Everything else must be clean.
 *
 *  - Layers: axe cannot read the contrast of text that another layer partly covers (the sticky jump
 *    bar, an open popover, a toast), and says "incomplete". The pairs themselves are tested in
 *    tests/unit/design/tokens.test.ts. A toast also covers page buttons for a few seconds by design,
 *    which trips the 24 px target-size rule on the buttons underneath.
 *  - Modals: Radix marks everything behind an open modal `aria-hidden` (data-aria-hidden) and traps
 *    focus, so the hidden page cannot be reached. Axe still reports hidden elements that contain
 *    focusable ones, and the (hidden) page heading.
 *  - Portals: overlays are drawn outside <main> by design, so the best-practice `region` rule does
 *    not apply to them.
 *  - A popover trigger's aria-controls points at content in a portal (or, while closed, not yet in the
 *    DOM), which is valid; axe marks that pattern "needs review".
 */
const OBSCURED =
  /partially obscured by another element|partially overlaps other elements|overlapped by another element/;
const BEHIND_MODAL = /data-aria-hidden="true"|data-radix-focus-guard/;
const PORTAL = /data-radix-|role="(?:dialog|alertdialog|menu|tooltip|listbox)"/;

interface Mode {
  /** A modal is open: everything behind it is hidden from assistive technology. */
  modal?: boolean;
  /** Some overlay is open or showing. */
  overlay?: boolean;
}

function accepted(
  rule: string,
  html: string,
  message: string,
  summary: string,
  mode: Mode,
): boolean {
  if (OBSCURED.test(message)) return true;
  if (rule === "region" && PORTAL.test(html)) return true;
  if (rule === "aria-valid-attr-value" && /aria-controls/.test(html) && /aria-haspopup/.test(html))
    return true;
  if ((mode.overlay || mode.modal) && rule === "target-size" && /partially obscured/.test(summary))
    return true;
  if (mode.modal && rule === "page-has-heading-one") return true;
  if (mode.modal && rule === "aria-hidden-focus" && BEHIND_MODAL.test(html)) return true;
  return false;
}

async function audit(page: Page, where: string, mode: Mode = {}) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();

  const violations = results.violations.flatMap((v) =>
    v.nodes
      .filter((n) => !accepted(v.id, n.html, n.any[0]?.message ?? "", n.failureSummary ?? "", mode))
      .map(
        (n) =>
          `${where} [${v.impact}] ${v.id}: ${n.target.join(" ")} => ${n.failureSummary?.split("\n")[1] ?? ""}`,
      ),
  );
  expect(violations).toEqual([]);

  const undecided = results.incomplete.flatMap((item) =>
    item.nodes
      .filter((node) => {
        const message = node.any[0]?.message ?? "";
        if (TRANSLUCENT.test(node.html) || UNDECIDABLE.test(message)) return false;
        return !accepted(item.id, node.html, message, node.failureSummary ?? "", mode);
      })
      .map(
        (node) => `${where} ${item.id}: ${node.html.slice(0, 90)} => ${node.any[0]?.message ?? ""}`,
      ),
  );
  expect(undecided).toEqual([]);
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    test("the whole page, at desktop width", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await openDesign(page);
      await audit(page, "page");
    });

    test("the whole page, at phone width (tables become cards)", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openDesign(page);
      await expect(page.locator('ul[aria-label="Employees"]')).toBeVisible();
      await audit(page, "phone");
    });

    test("the whole page with reduced motion", async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await openDesign(page);
      await audit(page, "reduced motion");
    });

    test("a dialog, open", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Open a dialog" }).click();
      await expect(page.getByRole("dialog", { name: "Add a location" })).toBeVisible();
      await audit(page, "dialog", { modal: true });
    });

    test("the inspector sheet, open", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Open the inspector" }).click();
      await expect(page.getByRole("dialog", { name: "Ada Lovelace" })).toBeVisible();
      await audit(page, "sheet", { modal: true });
    });

    test("a dialog as a bottom sheet on a phone", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openDesign(page);
      await page.getByRole("button", { name: "Open a dialog" }).click();
      await expect(page.getByRole("dialog", { name: "Add a location" })).toBeVisible();
      await audit(page, "dialog on phone", { modal: true });
    });

    test("the confirmation that asks for a name", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Delete permanently" }).click();
      await expect(page.getByRole("alertdialog")).toBeVisible();
      await audit(page, "confirm dialog", { modal: true });
    });

    test("a menu, open", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Actions" }).click();
      await expect(page.getByRole("menu")).toBeVisible();
      await audit(page, "menu", { modal: true });
    });

    test("a popover, open", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Open a popover" }).click();
      await expect(page.getByText("Why a 14-day wait?")).toBeVisible();
      await audit(page, "popover", { overlay: true });
    });

    test("the calendar, open", async ({ page }) => {
      await openDesign(page);
      await page.locator("#inputs").getByLabel("Start date", { exact: true }).first().focus();
      await page.keyboard.press("Alt+ArrowDown");
      await expect(
        page.getByRole("dialog", { name: "Choose start date" }).getByRole("grid"),
      ).toBeVisible();
      await audit(page, "calendar", { overlay: true });
    });

    test("a combobox list, open", async ({ page }) => {
      await openDesign(page);
      await page.locator('#inputs input[role="combobox"]').first().fill("e");
      await expect(page.getByRole("listbox")).toBeVisible();
      await audit(page, "combobox", { overlay: true });
    });

    test("a toast, showing", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Success with Undo" }).click();
      await expect(page.getByText("Leave approved").first()).toBeVisible();
      await audit(page, "toast", { overlay: true });
    });

    test("a tooltip, showing", async ({ page }) => {
      await openDesign(page);
      const button = page.getByRole("button", { name: "Hover or focus me" });
      // Scroll first: Radix closes a tooltip on any scroll, and focus() on an off-screen button scrolls.
      await button.scrollIntoViewIfNeeded();
      await button.focus();
      await expect(page.getByText("Shown on hover and on keyboard focus").first()).toBeVisible();
      await audit(page, "tooltip", { overlay: true });
    });
  });
}
