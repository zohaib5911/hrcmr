/** Public application through interview, accepted offer, scanned RTW evidence and employee conversion. */
import { API, csrfHeaders } from "../../support/accounts";
import { expect, test } from "../../support/fixtures";

import { BASE_URL } from "../helpers";

test("a public applicant is interviewed, accepts an offer and becomes an employee after verified RTW", async ({
  context,
  browser,
  page,
}) => {
  test.setTimeout(120_000);
  const api = context.request;
  const headers = await csrfHeaders(api);
  const stamp = Date.now();
  const title = `Line cook ${stamp}`;
  const requisition = await api.post(`${API}/requisitions`, {
    headers,
    data: { job_title: title, headcount: 1 },
  });
  expect(requisition.status(), await requisition.text()).toBe(201);
  const requisitionId = (await requisition.json()).id;
  expect(
    (
      await api.patch(`${API}/requisitions/${requisitionId}/status`, {
        headers,
        data: { status: "open" },
      })
    ).status(),
  ).toBe(200);

  const open = await api.post(`${API}/postings`, {
    headers,
    data: { requisition_id: requisitionId, title, visibility: "external", vacancies: 1 },
  });
  expect(open.status(), await open.text()).toBe(201);
  const openId = (await open.json()).id;
  const opened = await api.patch(`${API}/postings/${openId}/status`, {
    headers,
    data: { status: "open" },
  });
  expect(opened.status(), await opened.text()).toBe(200);
  const link = new URL((await opened.json()).public_link);
  const [, careers, company, slug] = link.pathname.split("/");
  expect(careers).toBe("careers");

  const closedTitle = `Closed role ${stamp}`;
  const closed = await api.post(`${API}/postings`, {
    headers,
    data: {
      requisition_id: requisitionId,
      title: closedTitle,
      visibility: "external",
      vacancies: 1,
    },
  });
  expect(closed.status(), await closed.text()).toBe(201);
  const closedSlug = (await closed.json()).slug;

  const visitor = await browser.newContext({ baseURL: BASE_URL });
  try {
    const page = await visitor.newPage();
    await page.goto(`/careers/${company}`);
    await expect(page.getByRole("link", { name: new RegExp(title) })).toBeVisible();
    await page.getByRole("link", { name: new RegExp(title) }).click();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await page.getByLabel("First name", { exact: true }).fill("Ivy");
    await page.getByLabel("Last name", { exact: true }).fill("Stone");
    await page.getByLabel("Email", { exact: true }).fill(`ivy-${stamp}@example.com`);
    await page.getByRole("checkbox", { name: /I agree that you may store my details/ }).check();
    await page.getByRole("button", { name: "Send application", exact: true }).click();
    await expect(page.getByText("Thank you for applying", { exact: true })).toBeVisible();

    const gone = await page.goto(`/careers/${company}/${closedSlug}`);
    expect(gone?.status()).toBe(404);
    const goneList = await page.goto(`/careers/${company}/${slug}-missing`);
    expect(goneList?.status()).toBe(404);
  } finally {
    await visitor.close();
  }

  await test.step("HR interviews the public applicant and records an accepted offer", async () => {
    const applications = await api.get(`${API}/applications`);
    expect(applications.status(), await applications.text()).toBe(200);
    const application = (await applications.json()).items.find(
      (item: { posting_id: string }) => item.posting_id === openId,
    );
    expect(application.applied_via).toBe("careers_page");
    await page.goto(`/recruitment/applications/${application.id}`);
    const convert = page.getByRole("button", { name: "Convert to employee", exact: true });
    await expect(convert).toBeDisabled();
    await page.getByRole("button", { name: "Move to Shortlisted", exact: true }).click();
    const interviews = page.getByRole("region", { name: "Interviews", exact: true });
    await interviews.getByLabel("Date and time", { exact: true }).fill("2026-12-01T10:00");
    await interviews.getByRole("button", { name: "Book interview", exact: true }).click();
    await expect(interviews.getByLabel("Outcome", { exact: true })).toBeVisible();
    const calendarDownload = page.waitForEvent("download");
    await interviews.getByRole("button", { name: "Add to calendar (.ics)", exact: true }).click();
    expect((await calendarDownload).suggestedFilename()).toMatch(/\.ics$/);
    await interviews.getByLabel("Outcome", { exact: true }).selectOption("passed");
    await expect(interviews.getByLabel("Outcome", { exact: true })).toHaveValue("passed");
    const offers = page.getByRole("region", { name: "Offers", exact: true });
    await offers.getByLabel("Role title", { exact: true }).fill(title);
    await offers.getByLabel("Salary (GBP)", { exact: true }).fill("32000");
    await offers.getByLabel("Start date (optional)", { exact: true }).fill("2026-12-07");
    await offers.getByRole("button", { name: "Save offer as draft", exact: true }).click();
    await offers.getByRole("button", { name: "Mark as sent", exact: true }).click();
    await offers.getByRole("button", { name: "Mark as accepted", exact: true }).click();
    await expect(offers.getByText("Accepted", { exact: true })).toBeVisible();
    await expect(convert).toBeDisabled();
    // Prove that bypassing the disabled button cannot create an employee without verified evidence.
    const refused = await api.post(`${API}/applications/${application.id}/convert`, {
      headers,
      data: { employee_number: `HIRE-${stamp}`, hire_date: "2026-12-07" },
    });
    expect(refused.status(), await refused.text()).toBe(422);
    expect((await refused.json()).error.code).toBe("CONVERT_NEEDS_VERIFIED_RTW");

    // Candidate RTW's compact UI has no evidence picker; bind a real, scanned file via the API.
    const proof = await api.post(`${API}/files`, {
      headers,
      multipart: {
        owner_type: "candidate",
        owner_id: application.candidate_id,
        file: {
          name: "candidate-rtw.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from(
            "%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n",
          ),
        },
      },
    });
    expect(proof.status(), await proof.text()).toBe(201);
    const file = await proof.json();
    expect(file.scan_status).toBe("clean");
    const me = await api.get(`${API}/auth/me`);
    expect(me.status(), await me.text()).toBe(200);
    const check = await api.post(`${API}/candidates/${application.candidate_id}/rtw-checks`, {
      headers,
      data: {
        check_type: "manual_list_a",
        check_date: new Date().toISOString().slice(0, 10),
        checked_by_user_id: (await me.json()).user.id,
        outcome: "verified",
        evidence_file_id: file.id,
      },
    });
    expect(check.status(), await check.text()).toBe(201);
    expect((await check.json()).status).toBe("verified");
    await page.reload();
    await expect(convert).toBeEnabled();
    await convert.click();
    const sheet = page.getByRole("dialog", { name: "Convert to employee", exact: true });
    await sheet.getByLabel("Employee number", { exact: true }).fill(`HIRE-${stamp}`);
    await expect(sheet.getByLabel("Work email", { exact: true })).toHaveValue(
      `ivy-${stamp}@example.com`,
    );
    await sheet.getByRole("button", { name: "Convert to employee", exact: true }).click();
    await expect(page).toHaveURL(/\/employees\/[0-9a-f-]+$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "Ivy Stone", exact: true }),
    ).toBeVisible();
    const employee = page.url().split("/").at(-1);
    const transferred = await api.get(`${API}/employees/${employee}/rtw-checks`);
    expect(transferred.status(), await transferred.text()).toBe(200);
    expect((await transferred.json()).status).toBe("verified");
    const repeat = await api.post(`${API}/applications/${application.id}/convert`, {
      headers,
      data: { employee_number: `DUPLICATE-${stamp}`, hire_date: "2026-12-07" },
    });
    expect(repeat.status(), await repeat.text()).toBe(409);
    expect((await repeat.json()).error.code).toBe("ALREADY_CONVERTED");
    const hired = await api.get(`${API}/applications/${application.id}`);
    expect(hired.status(), await hired.text()).toBe(200);
    expect((await hired.json()).stage).toBe("hired");
    const people = await api.get(`${API}/employees`);
    expect(people.status(), await people.text()).toBe(200);
    expect((await people.json()).employees).toHaveLength(1);
    const movedProof = await api.get(`${API}/files/${file.id}`);
    expect(movedProof.status(), await movedProof.text()).toBe(200);
    expect(await movedProof.json()).toMatchObject({ owner_type: "employee", owner_id: employee });
  });
});
