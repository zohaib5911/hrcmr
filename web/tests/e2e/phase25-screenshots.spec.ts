/** T22.4/T25.1/P25: exhaustive route evidence; observations are recorded for the design queue. */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, createSignedInAdmin, csrfHeaders } from "../support/accounts";
import { answerApi } from "../support/auth-screens";
import { ADMIN_ORIGIN, signInPlatformAdmin } from "../support/platform";

const ROOT = path.resolve(__dirname, "../../../docs/screenshots/phase-25");
const finalQA = process.env.FINAL_DESIGN_QA === "1";
const OUT = finalQA
  ? path.resolve(ROOT, "../final")
  : path.join(ROOT, process.env.DESIGN_AUDIT_STAGE ?? "before");
const widths = finalQA ? [390, 768, 1280, 1920] : [390, 1280];
type Screen = { source: string; route: string; group: string; key: string };
const screens: Screen[] = JSON.parse(readFileSync(path.join(ROOT, "routes.json"), "utf8"));
test.skip(!process.env.SCREENSHOTS, "Exhaustive design evidence is explicitly requested.");
test.use({ storageState: { cookies: [], origins: [] } });

async function seed(api: APIRequestContext) {
  const headers = await csrfHeaders(api);
  const post = async (route: string, data: unknown) => {
    const response = await api.post(`${API}${route}`, { headers, data });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  const employee = await post("/employees", {
    first_name: "Nadia",
    last_name: "Patel",
    employee_number: "AUDIT001",
    email: "nadia@example.com",
    hire_date: "2025-01-01",
  });
  const users = await (await api.get(`${API}/users`)).json();
  const me = users.users.find((u: { is_you: boolean }) => u.is_you);
  expect(
    (
      await api.put(`${API}/users/${me.id}/employee`, {
        headers,
        data: { employee_id: employee.id },
      })
    ).ok(),
  ).toBeTruthy();
  const policy = await post("/policies", {
    title: "Staff handbook 2026",
    category: "employee_handbook",
    confirmation_mode: "accept",
    audience_type: "everyone",
    accept_within_days: 14,
  });
  const course = (await (await api.get(`${API}/learning/courses`)).json()).find(
    (c: { slug: string }) => c.slug === "e2e-test-course",
  );
  await post("/learning/assignments", {
    course_ids: [course.id],
    scope: "named",
    employee_ids: [employee.id],
    due_on: "2026-12-01",
  });
  const assignment = (await (await api.get(`${API}/learning/assignments/own`)).json())[0];
  const req = await post("/requisitions", {
    job_title: "Care coordinator",
    headcount: 2,
    budget_from: "28000",
    budget_to: "32000",
    budget_per: "year",
  });
  expect(
    (
      await api.patch(`${API}/requisitions/${req.id}/status`, { headers, data: { status: "open" } })
    ).ok(),
  ).toBeTruthy();
  const posting = await post("/postings", {
    requisition_id: req.id,
    title: "Care coordinator",
    visibility: "external",
    vacancies: 2,
    description: "Help our care team plan reliable support for local families.",
  });
  const opened = await api.patch(`${API}/postings/${posting.id}/status`, {
    headers,
    data: { status: "open" },
  });
  expect(opened.ok()).toBeTruthy();
  const careers = new URL((await opened.json()).public_link).pathname;
  const candidate = await post("/candidates", {
    first_name: "Priya",
    last_name: "Shah",
    email: "priya@example.com",
    source: "Referral",
  });
  const application = await post("/applications", {
    candidate_id: candidate.id,
    posting_id: posting.id,
  });
  const register = (await (await api.get(`${API}/public/register/sitemap/0`)).json()).items.find(
    (s: { slug: string }) => s.slug === "stable-ltd",
  );
  const company = await (await api.get(`${API}/company`)).json();
  return {
    "/employees/[id]": `/employees/${employee.id}`,
    "/policies/[id]": `/policies/${policy.id}`,
    "/learning/assignments/[id]": `/learning/assignments/${assignment.id}`,
    "/recruitment/candidates/[id]": `/recruitment/candidates/${candidate.id}`,
    "/recruitment/applications/[id]": `/recruitment/applications/${application.id}`,
    "/careers/[company]": careers.split("/").slice(0, 3).join("/"),
    "/careers/[company]/[posting]": careers,
    "/sponsors/profile/[id]/[slug]": `/sponsors/profile/${register.stable_id}/${register.slug}`,
    "/sponsors/regions/[region]": "/sponsors/regions/london",
    "/sponsors/changes/[date]": "/sponsors/changes/2026-11-11",
    "/platform/companies/[id]": `/platform/companies/${company.company.id}`,
    "/compare/[category]": "/compare/hr",
    "/vs/[competitor]": "/vs/example",
  } as Record<string, string>;
}

async function observe(page: Page) {
  return page.evaluate(() => {
    const visible = (el: Element) =>
      el.getBoundingClientRect().width > 0 &&
      el.getBoundingClientRect().height > 0 &&
      getComputedStyle(el).visibility !== "hidden";
    const style = (el: Element) => {
      const s = getComputedStyle(el);
      return {
        tag: el.tagName,
        text: el.textContent?.trim().slice(0, 90),
        fontSize: s.fontSize,
        lineHeight: s.lineHeight,
        weight: s.fontWeight,
        background: s.backgroundColor,
        blur: s.backdropFilter,
        border: s.borderBottomWidth,
        shadow: s.boxShadow,
      };
    };
    return {
      title: document.title,
      headings: [...document.querySelectorAll("h1")].map(style),
      overflow: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      materials: [...document.querySelectorAll(".material-chrome,.material-sheet")]
        .filter(visible)
        .map(style),
      smallTargets: [...document.querySelectorAll("button,a,input,select")]
        .filter(visible)
        .filter((el) => {
          const r = el.getBoundingClientRect();
          return r.height < 32 || r.width < 32;
        })
        .slice(0, 15)
        .map((el) => ({
          text: (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 70),
          width: el.getBoundingClientRect().width,
          height: el.getBoundingClientRect().height,
        })),
      errors: [...document.querySelectorAll('[role="alert"]')]
        .filter(visible)
        .map((el) => el.textContent),
      font: getComputedStyle(document.body).fontFamily,
    };
  });
}

for (const colorScheme of ["light", "dark"] as const) {
  for (const width of widths) {
    test(`all routes ${colorScheme} ${width}`, async ({ browser }) => {
      test.setTimeout(1_800_000);
      mkdirSync(OUT, { recursive: true });
      const options = {
        colorScheme,
        viewport: { width, height: 900 },
        baseURL: "http://127.0.0.1:3100",
        storageState: { cookies: [], origins: [] },
      };
      const tenant = await browser.newContext(options);
      await createSignedInAdmin(tenant.request);
      const routes = await seed(tenant.request);
      const admin = await browser.newContext(options);
      const adminPage = await admin.newPage();
      await adminPage.route("https://admin.example.test:3100/_next/static/**", async (route) => {
        if (!["stylesheet", "font"].includes(route.request().resourceType())) return route.abort();
        const asset = await adminPage.request.get(
          route.request().url().replace("https://admin.example.test", "http://127.0.0.1"),
        );
        await route.fulfill({ response: asset });
      });
      await signInPlatformAdmin(adminPage, "owner");
      // Legacy course/rule/dossier SSR uses the tenant session as well as the platform cookie.
      const tenantCookie = (await admin.cookies(API)).find((c) => c.name === "brand_session");
      expect(tenantCookie).toBeTruthy();
      await admin.addCookies([{ ...tenantCookie!, domain: "admin.example.test", path: "/" }]);
      const publicContext = await browser.newContext(options);
      const publicPage = await publicContext.newPage();
      // Evidence writes can trigger dev HMR. Keep the loaded showcase stable while capturing it.
      await publicPage.routeWebSocket("**/_next/webpack-hmr**", () => {});
      const authContext = await browser.newContext(options);
      const authPage = await authContext.newPage();
      await authPage.goto("/login");
      await answerApi(authPage);
      const tenantPage = await tenant.newPage();
      const results: unknown[] = [];
      try {
        for (const screen of screens) {
          const page =
            screen.group === "app"
              ? tenantPage
              : screen.group === "admin"
                ? adminPage
                : screen.group === "auth"
                  ? authPage
                  : publicPage;
          let route = routes[screen.route] ?? screen.route;
          if (route === "/reset-password" || route === "/accept-invite") route += "?token=example";
          const url =
            screen.group === "admin"
              ? ADMIN_ORIGIN + (route.replace(/^\/platform/, "") || "/")
              : screen.group === "dev"
                ? "http://localhost:3101" + route
                : route;
          const response = await page.goto(url);
          await page.waitForLoadState("networkidle");
          await page.evaluate(() => document.fonts.ready);
          // Capture stable layout, including genuine designed empty/error states.
          await expect(page.locator("body")).not.toBeEmpty();
          if (screen.group === "public") {
            const reject = page.getByRole("button", { name: "Reject all", exact: true });
            if (await reject.isVisible()) await reject.click();
          }
          await page.mouse.move(0, 0);
          await page.evaluate(() => {
            if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
          });
          const filename = `${screen.key}-${colorScheme}-${width}.png`;
          await page.screenshot({
            path: path.join(OUT, filename),
            fullPage: true,
            animations: "disabled",
          });
          const metrics = await observe(page);

          // Admin JS is blocked by production CSP on local HTTP; axe injection cannot run there.
          const axe =
            screen.group === "admin"
              ? null
              : (
                  await new AxeBuilder({ page })
                    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
                    .analyze()
                ).violations.map((v) => ({
                  id: v.id,
                  impact: v.impact,
                  count: v.nodes.length,
                  targets: v.nodes.slice(0, 3).map((n) => n.target),
                }));
          results.push({
            ...screen,
            url: page.url(),
            status: response?.status(),
            filename,
            ...metrics,
            axe,
          });
          writeFileSync(
            path.join(OUT, `observations-${colorScheme}-${width}.json`),
            JSON.stringify(results, null, 2) + "\n",
          );
          console.log(`captured ${results.length}/${screens.length}: ${screen.route}`);
        }
      } finally {
        await Promise.all([
          tenant.close(),
          admin.close(),
          publicContext.close(),
          authContext.close(),
        ]);
      }
    });
  }
}

// Surfaces need overlapping content to judge the glass; route screenshots alone cannot show this.
for (const colorScheme of ["light", "dark"] as const) {
  for (const width of widths) {
    test(`material overlays ${colorScheme} ${width}`, async ({ browser }) => {
      test.setTimeout(120_000);
      const context = await browser.newContext({
        colorScheme,
        viewport: { width, height: 900 },
        baseURL: "http://127.0.0.1:3100",
        storageState: { cookies: [], origins: [] },
      });
      await createSignedInAdmin(context.request);
      const page = await context.newPage();
      const results: unknown[] = [];
      const capture = async (name: string) => {
        await page.evaluate(() => document.fonts.ready);
        const dialog = page.getByRole("dialog");
        await expect(dialog).toBeVisible();
        await page.screenshot({
          path: path.join(OUT, `overlay-${name}-${colorScheme}-${width}.png`),
          animations: "disabled",
        });
        results.push({ name, ...(await observe(page)) });
        await page.keyboard.press("Escape");
        await expect(dialog).toBeHidden();
      };
      try {
        await page.goto("/dashboard");
        await page.keyboard.press("Control+k");
        await expect(page.getByPlaceholder("Search pages")).toBeVisible();
        await capture("command-palette");
        await page
          .getByRole("button", { name: /^Notifications/ })
          .first()
          .click();
        await capture("notifications");
        await page.goto("/company");
        await page.getByRole("button", { name: /^Details/ }).click();
        await capture("company-sheet");
        await page.goto("/");
        const reject = page.getByRole("button", { name: "Reject all", exact: true });
        if (await reject.isVisible()) await reject.click();
        if (width === 390) {
          await page.getByRole("button", { name: "Menu", exact: true }).click();
          await capture("marketing-menu");
        }
        await page.evaluate(() => window.scrollTo(0, 350));
        await page.screenshot({
          path: path.join(OUT, `overlay-scrolled-marketing-nav-${colorScheme}-${width}.png`),
          animations: "disabled",
        });
        results.push({ name: "scrolled-marketing-nav", ...(await observe(page)) });
        writeFileSync(
          path.join(OUT, `overlays-${colorScheme}-${width}.json`),
          JSON.stringify(results, null, 2) + "\n",
        );
      } finally {
        await context.close();
      }
    });
  }
}
