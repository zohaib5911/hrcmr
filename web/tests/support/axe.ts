/**
 * The accessibility check used by every browser test that wants one: axe-core against WCAG 2.2 A and
 * AA plus best practice, with a short, explained list of results that are accepted (below).
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

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

export interface Mode {
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
  // Whatever an open overlay shows lives in a portal outside <main>; nothing else may.
  if (rule === "region" && (PORTAL.test(html) || mode.modal || mode.overlay)) return true;
  if (rule === "aria-valid-attr-value" && /aria-controls/.test(html) && /aria-haspopup/.test(html))
    return true;
  if ((mode.overlay || mode.modal) && rule === "target-size" && /partially obscured/.test(summary))
    return true;
  // Behind a modal, Radix hides <main> and with it the page heading.
  if (mode.modal && (rule === "page-has-heading-one" || rule === "landmark-one-main")) return true;
  if (mode.modal && rule === "aria-hidden-focus" && BEHIND_MODAL.test(html)) return true;
  return false;
}

export async function audit(page: Page, where: string, mode: Mode = {}) {
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
