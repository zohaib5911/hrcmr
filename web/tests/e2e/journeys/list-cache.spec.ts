/**
 * O6.1.6: going back to a list shows it at once, from this tab's last answer, while a fresh answer
 * loads in the background. A row's detail is fetched ahead when the pointer is over it.
 */
import { API, csrfHeaders } from "../../support/accounts";
import { expect, test } from "../../support/fixtures";

test("list, then a candidate, then back: the list is there at once and refreshes behind", async ({
  page,
  context,
}) => {
  const api = context.request;
  const stamp = Date.now();
  const created = await api.post(`${API}/candidates`, {
    headers: await csrfHeaders(api),
    data: { first_name: "Cache", last_name: `Back${stamp}` },
  });
  expect(created.status(), await created.text()).toBe(201);
  const candidateId = (await created.json()).id as string;
  const name = `Cache Back${stamp}`;

  await page.goto("/recruitment?tab=candidates");
  const table = page.getByRole("grid", { name: "Candidates" });
  const row = table.getByRole("row").filter({ hasText: name });
  await expect(row).toBeVisible();

  // Pointing at the row fetches the profile ahead, so it opens already filled in.
  const ahead = page.waitForRequest((request) =>
    request.url().endsWith(`/api/v1/candidates/${candidateId}`),
  );
  await row.hover();
  await ahead;
  await row.click();
  await expect(page).toHaveURL(new RegExp(`/recruitment/candidates/${candidateId}$`));
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();

  // Back: the candidate list (the tab is in the address) is shown from the cache at once, with no
  // skeleton, and a fresh answer is still fetched.
  const refreshed = page.waitForRequest(
    (request) => new URL(request.url()).pathname === "/api/v1/candidates",
  );
  await page.goBack();
  await expect(page).toHaveURL(/\/recruitment\?tab=candidates$/);
  await expect(row).toBeVisible({ timeout: 1_000 });
  await expect(table.locator(".skeleton")).toHaveCount(0);
  await refreshed;
});
