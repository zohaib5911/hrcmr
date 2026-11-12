# Marketing SEO checks

Set `NEXT_PUBLIC_SITE_URL` to the public HTTPS origin before building for deployment. Canonicals,
social cards and sitemap URLs use this configured value, never the request Host header. The local
fallback is `http://localhost:3000`.

Use `pageMetadata(path, title, description)` from `web/lib/seo.ts` for each published public page.
Add its path and breadcrumb label to `marketingPages` in the same module. This catalogue controls
the sitemap and the exact paths allowed by robots; scripts and marketing assets remain crawlable.
Unpublished comparisons and draft legal documents remain excluded. Add directory sitemap shards
with the Phase 20 public sponsor routes when that dataset and those routes are available.

Organization, WebSite, SoftwareApplication and BreadcrumbList structured data are rendered on the
server with the request CSP nonce. Home and pricing FAQs describe the same questions and answers
as the visible accordion. No ratings or registration details are invented. The Open Graph PNG is
generated from brand configuration at `/opengraph-image` and shared by public pages.

There is no configured analytics vendor or tracking endpoint. Accepting optional cookies does not
load tracking. Any future integration must subscribe to the consent manager, honour rejection and
withdrawal, update the cookie policy and its consent version, and stay outside the signed-in app.

Run focused checks from `web/`:

```sh
pnpm exec vitest run lib/seo.test.ts lib/cookie-consent.test.ts
pnpm lint
pnpm typecheck
```

Use the coordinator bus's `serial` command around every build, Playwright run and Lighthouse run.
Build with the intended public URL, then run `pnpm exec playwright test --config playwright.seo.config.ts`
to validate public SEO without starting account/API fixtures. The regular Playwright configuration
also includes these browser tests.

For Lighthouse, serve that production build on port 3100 (`PORT=3100 pnpm start`) and run
`pnpm audit:marketing` under the same serial lock. It uses Chromium installed by Playwright,
Lighthouse's default mobile simulation, and a minimum score of 95 in performance, accessibility,
best practices and SEO for all ten core marketing pages. Optional path arguments limit a rerun to
changed pages; `LIGHTHOUSE_ORIGIN` changes the origin. Raw reports and scores go to `.lighthouseci/`
(ignored). The runner fails on scores below 95 or runtime errors. Use production builds, with no
browser extensions or concurrent builds, for comparable results.

The recorded T18.3 run is in `docs/qa/marketing-lighthouse.json`: all ten pages meet the threshold.
The dependency audit at that run had no high/critical advisories. It reported two moderate tooling
advisories: Lighthouse → Sentry → glob (AbortSignal cancellation bypass) and the existing
ESLint → TypeScript parser → minimatch path (globparts amplification). Neither is shipped as an
application runtime dependency. Recheck the locked tools when their upstream fixes are available.
