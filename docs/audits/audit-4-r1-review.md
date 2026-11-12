# AUDIT-4 round 1 review evidence

Snapshot: b660e57. Assignment: T18.1–P20. Review includes all Phase 18–20 implementations, although audit-pass-3 already contains most of them: AUDIT-3 explicitly excluded those additions. Literal audit-pass-3..HEAD also reviewed for phase-gate changes. The parallel worktree rule overrides audit.md's old instruction to switch the coordinator dev branch.

Task risk: T19.1 B; T19.2–T19.14, T19.16 and T20.1 S!; remaining marketing, resource and register tasks/gates S (T19.15 explicitly S). Required verification and spec/code/test review in progress.

## Implementation review (in progress)

- T18.1–T18.4: reviewed public contact input/output, rate limit and Turnstile; marketing route list, config pricing, legal-draft/consent implementation, unpublished comparisons, canonical/JSON-LD/sitemaps/robots. Public writes retain hashed connection data and plain escaped content. Cookie storage is guarded and defaults optional consent off.
- T19.1–T19.18: read all thirteen calculator modules and their tests, risk export/storage implementation, shared results template, source manifests, six compiled MDX guides, build-time MDX guard, self-test, template manifest/review gate and download path validation. No calculator input network/storage calls except the explicitly local risk draft. Candidate defects require targeted probes below.
- T20.1–T20.5: reviewed discovery, redirect allowlist and size bounds, advisory transaction lock/idempotency, snapshot diffs, scheduler, geo parsers/apply functions, public register queries/POST, admin status/rerun and tests. Geo apply functions are called only in tests/e2e seeding, not production jobs/CLI. The router-wide read limiter added by c955b58 is absent at HEAD; only explore still calls a read limiter. Region-map geometry is explicitly schematic; owner already scheduled replacement in T25.2, so do not create duplicate work for its shape.
- Hidden-cheating scan across phase files from f1ef357 found documented FastAPI/SQLAlchemy typing noqa lines, effect hydration eslint exceptions and screenshot-only opt-ins. No removed test assertions in that range. No new product-test skips found. Existing unit tests encode some incorrect calculator behavior (health-care ISC exemption); not evidence of deliberate test fraud.

## Live primary-source checks (2026-11-12 UTC / 2026-11-13 PKT)

- RTW tool: [October employer guide](https://assets.publishing.service.gov.uk/media/6ad9dfe29ea4857e15ab3294/Employer_s_guide_to_right_to_work_checks.pdf), verified publication edition, employee commencement 2008-02-29, extended commencement 2026-10-01, two-year post-employment retention. Relevant scheme dates and evidence handling match the module.
- Sponsor cost: [licence fees](https://www.gov.uk/uk-visa-sponsorship-employers/apply-for-your-licence), checked Worker fees 611/1682 and two-of-three size limits; [ISC](https://www.gov.uk/uk-visa-sponsorship-employers/immigration-skills-charge), checked first/extra blocks 480/240 and1320/660, exemption conditions; [CoS](https://www.gov.uk/uk-visa-sponsorship-employers/certificates-of-sponsorship), Worker525; [IHS](https://www.gov.uk/healthcare-immigration-application/how-much-pay), adult1035, under18 776 and partial-year conditions; [visa fees](https://www.gov.uk/skilled-worker-visa/how-much-it-costs) linked in local source files. Candidate ISC exemption and visa-duration bugs below.
- Reporting deadline: [Part3](https://www.gov.uk/government/publications/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance-accessible), confirmed C1.19 trigger day10 plus10 working days, C1.46 role changes10, C2.3 organisation20 with named personnel exception.
- Visa eligibility: [Appendix Skilled Worker](https://www.gov.uk/guidance/immigration-rules/immigration-rules-appendix-skilled-worker), confirmed A41700/B37500/C33400, 90/80/70% options and B2 requirement. Reviewed local occupation table parsing; thresholds/funds/hour bases are hardcoded in the module despite T19's data-only rule.
- Settlement/citizenship: [worker overview](https://www.gov.uk/indefinite-leave-to-remain-tier-2-t2-skilled-worker-visa), [standard citizenship](https://www.gov.uk/apply-citizenship-indefinite-leave-to-remain), [British spouse citizenship](https://www.gov.uk/apply-citizenship-spouse). Local normalized milestones reviewed for5-year worker settlement, standard5-year residence plus12 settled months, spouse3-year residence with no12-month wait; outputs explicitly conditional, never an eligibility verdict.
- Settlement salary: [salary requirements](https://www.gov.uk/indefinite-leave-to-remain-tier-2-t2-skilled-worker-visa/salary-requirements), confirmed41700 usual,33400 ISL,31300 transitional and25000 relevant exception; source explicitly requires the going rate too. Candidate null-going-rate failure below.
- Holiday: [entitlement](https://www.gov.uk/holiday-entitlement-rights), confirmed5.6 weeks,28-day cap,3-day week16.8 days; [accrual](https://www.gov.uk/holiday-entitlement-rights/calculate-leave-entitlement), checked12.07% and whole-hour half-up treatment.
- Take-home: [HMRC2026–27](https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027), checked PA12570, primary NI12570, UEL50270 and20/40/45% bands; [tax codes](https://www.gov.uk/tax-codes/what-your-tax-code-means), D0 higher rate and Scottish codes have distinct mappings. Candidate incorrect flat-code mappings below.
- Employer cost: same HMRC source, checked secondary threshold5000, under21/under25 thresholds50270 and standard employer rate15%; [pension](https://www.gov.uk/workplace-pensions/what-you-your-employer-and-the-government-pay), checked qualifying earnings6240–50270, employer minimum3%, total8%.
- Redundancy: [GB source](https://www.gov.uk/redundancy-your-rights/redundancy-pay), confirmed2-year minimum,20-year service cap, age weights0.5/1/1.5. Module validates jurisdiction/date coverage and uses separate NI rates/rules.
- Notice: [GB notice](https://www.gov.uk/redundancy-your-rights/notice-periods), confirmed1-month service,1week before2years and12week cap. Month-end calendar arithmetic needs a probe.
- SSP: [entitlement](https://www.gov.uk/statutory-sick-pay/what-youll-get), confirmed123.25 weekly cap,80% of AWE,28week maximum; [HMRC manual guide](https://www.gov.uk/guidance/statutory-sick-pay-manually-calculate-your-employees-payments), Sunday–Saturday weeks; [HMRC2026–27](https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027) payment tables require partial-week penny checks. Module never enforces valid_to.
- Minimum wage: [rates](https://www.gov.uk/national-minimum-wage-rates), checked2026 adult12.71/18–20 10.85/under18+apprentice8;2027 announced rates separate. Historical age-band selection reviewed against stored dated periods. No invented published rate found in these spot checks.

## Ordered verification checkpoint

API Ruff and format pass (556 files); mypy passes (492 source files). Required full API suite:1363 passed /0failed /0skipped in622.57s, under the shared serial lock. Stack was reachable; Docker is unavailable in the agent jail, so no stack restart was necessary. RLS CLI passed on a fresh migrated throwaway database, which was removed afterwards. First scratch CLI launch omitted required test settings and failed before catalog inspection; supplied the existing build_settings-generated test environment and reran the CLI successfully. This was audit-harness setup, not a product failure; no real credentials used.

Web ordered checks pass: lint, typecheck, full Vitest, generated API client, production build and bundle scan. Literal plan L1479 review also found the shared calculator frame lacks specified breadcrumb/badge, presets/steps, explanations/FAQ/CTA/related tools; split its frame and two calculator groups into separate tasks. These are specified interactions/content, not an unsolicited visual redesign. Added task dependencies so the rate-limit repair lands first and overlapping calculator/enrichment files are handled in order. Optional Companies House bulk matching also has no production caller/flag, so it has a separate fix task rather than being silently bundled into geocoding.

Additional T20.5 review: API `register_status` requires platform read access and `run_register` requires jobs-run access, with audited allow-listed enqueue and reason validation; existing tests cover tenant denial, populated/empty status and audited queueing. However, the corresponding back-office page/actions do not exist in the frontend (no platform component/page references either endpoint). Recorded a dedicated UI fix, using the same session/CSP test pattern as the existing jobs screen.

Cross-mode holiday review found an additional concrete defect: regular-days mode correctly caps a6day week at28days, but regular-hours mode has no days/week input and always grants5.6weeks. For45hours over6equal days it reports252hours rather than210; added a separate bounded fix and a diagnostic case. Final candidate count is now21 (1P0/19P1/1P2), pending diagnostic execution.

## Required browser failure and permitted one-line correction

The full browser run found one P0 failure: `shell.spec.ts:66`, light390px, axe `scrollable-region-focusable` incomplete on the employee-view filter wrapper (`web/components/employees/employees-page.tsx:143`, `max-w-full overflow-x-auto`). The scrollable wrapper lacked a keyboard focus stop; all child radios can carry roving negative tab indices during this state. Under audit.md's explicit one-line CI correction exception, added only `tabIndex={0}` to that wrapper; no assertion, rule or skip was changed. Read web/AGENTS.md and the installed Next accessibility guide before the edit. Targeted lint/types/unit and all shell accessibility browser cases will verify it after diagnostics. The initial full-run failure remains reported separately from those post-fix checks.

## Independent diagnostic results

These scratch acceptance probes are separate from the required suites. They intentionally asserted the missing correct behavior and reproduced defects; their failures are evidence for the listed fix tasks, not a claim that the existing suites caught them. Temporary test files were removed after execution; assertions/rules in the committed tests were unchanged.

Five public-read probes forced `RateLimiter.hit` to deny and requested regions, London detail, changes, sitemap count and sitemap page. All five returned200 instead of429 (5 failed in9.09s), confirming C4.1.1. The same shared module also serves profiles; inspect every read family when restoring the dependency.

A fresh migrated-database fixture probe imported exact first.csv then second.csv on2026-11-10, committing each import. The Stable Ltd profile still returned only its morning A-rated Skilled Worker entry, although its changes contained the later B-rating and added Global Business Mobility route. The bulletin list contained two rows for2026-11-10, with3/0/net3 and2/2/net0 respectively. Restoring exact first.csv on2026-11-11 returned `unchanged`; only2publications remained and current sponsors stayed Stable Ltd, Example Care Limited and New Ltd (state B). This confirms both C4.1.2 and C4.1.4 without altering fixture bytes. The probe exited0 after reporting observations; its database was removed.

Thirteen calculator acceptance probes failed on the exact observed differences below (one scratch file,13 failed,569ms). Cases call the real pure modules, not mocks.

| Case | Observed | Required / source basis |
| --- | --- | --- |
| England D0, annual30000 | tax6000 |12000; D0 higher rate |
| Scotland SBR, annual30000 | tax5700 |6000; BR basic rate |
| Scotland SD1, annual30000 | tax14400 |12600; SD1 higher rate |
| 0T, annual30000 | tax5998.20 |6000; no allowance |
| Health/Care nurse2231, large sponsor,24months | ISC0 |2640; no blanket health-care exemption |
| ILR3214, usual branch | numeric41700 | review; standard going rate absent |
| SSP7qualifying days,2sick days |35.21 |35.22 in HMRC payment table |
| Notice Jan31→Feb28 | less than1month | calendar-month completion |
| Risk draft with null organisation/null hazard | accepted object | reject/recover safely |
| Reporting event2018-12-24 | deadline2019-01-08 | refuse: holidays start2019 |
| CoS12months, ordinary Skilled Worker | IHS1035 | estimated visa includes14days;1552.50 at next half-year block |
| Table3 midwifery nurse2231 | explicitly ineligible | supported calculation or needs-review state |
|45weekly hours over6equal days |252hours leave |210hours under28day cap; current API lacks the working-days input |

The6-day SSP examples conflict across two GOV.UK pages: the manual guide rounds a daily amount in its prose example, whereas the employer rates page provides the exact partial-week payment table. C4.1.12 specifies the dated payment table (e.g.4days82.17) as the calculator evidence and requires documenting that rounding basis; do not claim the two publications agree.

Latest dev CI queried after the required browser run:43302217904 atfa331d0 passed; the earlierb660e57 run was cancelled and43298198217 atfea9f9d passed. No CI waiting was performed.

## Final verification and result

The required full browser run ended485passed /1failed /328expected screenshot-only skips in17.1minutes. The one failure was the employee filter scroller described above. One-line fix commit:c221577. After that fix, lint/typecheck pass; employee-list unit6passed; rebuilding through the production browser runner and running all shell accessibility cases gave9passed (8theme/width cases plus setup) in37.5seconds. The complete suite was not rerun, per the audit's once-only rule; the original failure is not rewritten as a full-suite pass.

SSP conflict decision is recorded through the agent bus (C4.1.12, dev decision commit5f0473f). Final read-only CI query still lists43302217904 atfa331d0 as successful, with the priorb660e57 cancelled andfea9f9d successful. Did not wait for CI. Generated data-model freshness is covered by the passing full API test; generated API types passed the explicit web check.

Result: FIX NEEDED. Open findings1P0 /19P1 /1P2,21total, each with independent fix/verification steps in changesneeded.md. A further P0 required-browser finding was resolved by the documented one-line exception. AUDIT-4 stays unticked. The fix dependency graph contains21unique reachable tasks with no missing dependencies or cycles; every task follows C4.1.1 directly or transitively. No new owner decision/credential is needed for this audit. Existing human template/legal review and parked Stripe credentials remain unchanged.
