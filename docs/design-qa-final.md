# Phase 22 final design QA

T22.4 · 13 Nov 2026 · application baseline `9bf80ac` (see capture branch ancestry for the exact dev revision).

This is the Phase 22 review before the planned Phase 25 visual work. “Final” identifies the Phase 22 evidence directory; it does not mean the known design findings are resolved or that deployment acceptance has passed.

## Scope and reproduction

The [offline gallery](screenshots/final/index.html) covers the [141-case inventory](screenshots/phase-25/routes.json), representing all 127 page files, including legal/guide variants, seeded detail routes, unpublished comparison 404s and development design pages. Every case is captured at **390, 768, 1280 and 1920 px**, in **light and dark**, with a 900 px viewport height and full-page PNGs. Separate captures cover the command palette, notifications, company edit sheet, mobile marketing menu and scrolled public navigation.

```sh
bash /home/zohaib/cmr_hr/.agent/bus.sh serial -- bash -c \
  'cd web && FINAL_DESIGN_QA=1 SCREENSHOTS=1 pnpm exec playwright test phase25-screenshots --project=production'
node web/scripts/final-design-gallery.mjs
```

The existing Phase 25 harness still defaults to its original two widths and before/after directories. The final mode broadens widths and selects `docs/screenshots/final/`. The gallery generator checks that every inventory key has one observation and the expected PNG in each state, that routes return 200 except the two intentionally unpublished comparison templates (404), and that every expected overlay was captured. JSON observations retain axe findings, page overflow, headings/type, material styles and small-target candidates rather than silently dropping design defects.

## Checklist review

| Spec §5.12 check | Review and disposition |
| --- | --- |
| Light/dark at four widths | Eight route passes; each screen has eight linked PNGs. |
| 4 px spacing, aligned text, headings | Shared app canvas/card/row spacing remains consistent. Title sizing, breadcrumb crowding, public reading measure and legacy admin frames remain findings A/C/F in the [design audit](design-audit.md#fix-queue-largest-footprint-first). The four-width evidence extends the earlier mobile/desktop baseline. |
| One primary action; destructive confirmation | Empty lists repeat header and empty-state actions (finding E). Destructive confirmation behaviour is covered by existing journey tests, not inferred from screenshots. |
| Loading, empty, error and success states | Captures include seeded employee/candidate/application/policy/course records, real empty lists, auth presentation fixtures and intentional public 404s. Layout-specific loading skeletons and profile fallback remain findings B/K/L. This pass does not exercise every asynchronous transition or every tab. |
| Keyboard, focus, Escape | Overlay captures assert the dialog is visible and Escape dismisses command palette, notifications, company sheet and mobile marketing menu. Main-flow tab/landmark/skip-link and reduced-motion checks are in T22.3 `a11y-pages.spec.ts`. This pass is not an exhaustive manual keyboard audit of every control. |
| No serious/critical axe findings | See measured results below. Admin HTTP screenshots cannot run injected axe; HTTPS admin checks remain deployment/P25 acceptance work. |
| Copy, full-text disclosure, tabular numbers | UK-date presentation, truncation without disclosure, status casing and the recruitment stage overlap remain findings D/G/H/I; shared table/KPI numbers use tabular figures. |
| Motion/reduced motion | Screenshots disable animations for stable evidence; they cannot prove frame rate or motion quality. T22.3 checks reduced motion. Dialog entry-scale polish remains finding M. |
| Calm composition | Existing material recipes and shared cards are coherent. The audit already assigns the reusable composition gaps to T25.2/T25.4–T25.6; this evidence change does not duplicate those implementation blocks. |

## Additional viewport observations

At 768 px, the employee list keeps its 260 px desktop sidebar, leaving a narrow main column. The Right to Work filter wraps tightly and competes with search/archive controls; the tabs and table scroll within their own containers. [Tablet employee list](screenshots/final/app-employees-light-768.png). T25.5 should wrap the shared list toolbar coherently at tablet widths, retaining intentional horizontal table scrolling and accessible labels. This is a composition follow-up even when document overflow is zero. The admin audit table also demonstrates why finding F needs a shared responsive frame rather than isolated page styling.

Visual spot checks include the mobile dashboard and recruitment detail, tablet employee list/admin audit, 1920 px recruitment detail, dark mobile company settings and dark desktop public register. The gallery provides the complete evidence matrix; these sampled visual checks do not claim manual inspection of every pixel in every image.

## Evidence limits

Accounts are synthetic test sign-ups with isolated tenant records; public register data comes from saved fixtures. Invitation/MFA-enrolment views use the existing auth presentation fixtures. No live user data or real payment provider is involved.

Admin evidence has the same local HTTP limitation recorded in the Phase 25 audit and decision C3.1.10: the harness relays upgraded static CSS/fonts only, while production CSP continues to block scripts. These images prove styled SSR appearance; client-only panels can remain loading. They do not prove hydrated admin interaction or accessibility. No production security policy was relaxed.

Full-page images place fixed navigation at its viewport position within a longer page. The bar appearing part-way down a full-page image is a capture artefact; the page is scrollable behind it. Small-target observations include inline links and are review candidates, not automatic accessibility failures. Initial stable route screenshots do not cover every form error, record status, modal or loading transition; richer earlier phase evidence and focused journeys remain relevant.

## Measured results

- **Playwright: 17 passed in 22.4 minutes** (1 authentication setup, 8 exhaustive route passes, 8 overlay passes), under the shared serial lock. An earlier interrupted attempt exposed the dev hot-refresh loop; the completed run isolates that connection and recaptures the full matrix.
- **1,128 route PNGs + 34 overlay PNGs = 1,162 screenshots**, with matching observations and an offline gallery. All 127 page files map to the 141-case inventory; no missing or extra source files.
- **992 axe scans, 0 violations**; the 17 admin cases in each of eight passes are explicitly excluded because local HTTP CSP blocks injected scripts. No claim of admin axe coverage is made.
- **0 document overflows** across all 1,128 route observations. Internal table/tab scrolling and the tablet toolbar composition finding remain distinct review items.
- **26 successful Escape dismissals** across modal overlay checks. Eight additional screenshots show scrolled public navigation.
- **16 expected 404 observations** (two unpublished comparison templates × eight states); every other route observation returned 200.
- Gallery validation checks all route keys/statuses and expected route/overlay PNGs. PNG signatures/dimensions passed for all 1,162 files; every gallery image and report link resolves locally.
- Full web lint and TypeScript checks passed. Production build succeeded as part of the serialized Playwright run. No full suite was run in this block; P22 owns that gate check.
