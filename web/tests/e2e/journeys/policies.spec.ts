/** T10.3 policy send through the wizard, an employee's typed signature, the admin's Signed row, and /policies closed to employees. */
import { API, csrfHeaders, newAccount, waitForMail } from "../../support/accounts";
import { expect, test } from "../../support/fixtures";

import { BASE_URL } from "../helpers";

const PDF = Buffer.from(
  "%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n" +
    "2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n",
);

test("send a policy, the employee signs it, the admin sees Signed, and the employee cannot open /policies", async ({
  page,
  context,
  browser,
}) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const stamp = Date.now();
  const title = `Code of conduct ${stamp}`;
  const employeeEmail = `nia-policy-${stamp}@example.com`;
  const person = await api.post(`${API}/employees`, {
    headers,
    data: {
      first_name: "Nia",
      last_name: "Policy",
      employee_number: `POL${stamp}`,
      email: employeeEmail,
      hire_date: "2025-01-01",
    },
  });
  expect(person.status(), await person.text()).toBe(201);
  const employee = (await person.json()).id as string;

  const invite = await api.post(`${API}/users/invitations`, {
    headers,
    data: { first_name: "Nia", last_name: "Policy", email: employeeEmail, role: "employee" },
  });
  expect(invite.status(), await invite.text()).toBe(201);
  const mail = await waitForMail(api, employeeEmail, "You have been invited");
  const token = /token=([\w-]+)/.exec(mail)?.[1] ?? "";
  expect(token).not.toBe("");

  const member = await browser.newContext({ baseURL: BASE_URL });
  try {
    const accepted = await member.request.post(`${API}/auth/invitations/${token}/accept`, {
      headers: await csrfHeaders(member.request),
      data: {
        first_name: "Nia",
        last_name: "Policy",
        password: newAccount("member").password,
        accept_terms: true,
      },
    });
    expect(accepted.status(), await accepted.text()).toBe(200);

    const users = (await (await api.get(`${API}/users`)).json()).users as {
      id: string;
      email: string;
    }[];
    const invitee = users.find((user) => user.email === employeeEmail);
    expect(invitee, "the invited person is listed").toBeDefined();
    const linked = await api.put(`${API}/users/${invitee?.id}/employee`, {
      headers,
      data: { employee_id: employee },
    });
    expect(linked.status(), await linked.text()).toBe(200);

    const created = await api.post(`${API}/policies`, {
      headers,
      data: {
        title,
        category: "code_of_conduct",
        confirmation_mode: "sign",
        audience_type: "named",
        audience_ids: [employee],
        accept_within_days: 14,
      },
    });
    expect(created.status(), await created.text()).toBe(201);
    const policy = (await created.json()).id as string;
    const uploaded = await api.post(`${API}/policies/${policy}/file`, {
      headers,
      multipart: { file: { name: "code.pdf", mimeType: "application/pdf", buffer: PDF } },
    });
    expect(uploaded.status(), await uploaded.text()).toBe(200);
    await expect
      .poll(
        async () =>
          (await (await api.get(`${API}/policies/${policy}`)).json()).scan_status as string,
        { timeout: 60_000 },
      )
      .toBe("clean");

    await page.goto(`/policies/${policy}`);
    await page.getByRole("button", { name: "Continue setup", exact: true }).click();
    const sheet = page.getByRole("dialog", { name: "Continue policy", exact: true });
    await sheet.getByRole("button", { name: "Continue", exact: true }).click();
    await sheet.getByRole("button", { name: "Continue", exact: true }).click();
    await sheet.getByRole("button", { name: "Send to 1 person", exact: true }).click();
    await expect(sheet).toBeHidden();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();

    const memberPage = await member.newPage();
    await memberPage.goto("/my-documents");
    await expect(memberPage.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await memberPage
      .getByRole("checkbox", { name: "I have read this document.", exact: true })
      .check();
    await memberPage.getByLabel("Type your full name to sign", { exact: true }).fill("Nia Policy");
    await memberPage.getByRole("button", { name: "Sign and confirm", exact: true }).click();
    await expect(
      memberPage.getByRole("button", { name: "View receipt", exact: true }),
    ).toBeVisible();

    await memberPage.goto("/policies");
    await expect(
      memberPage.getByText("Policies are for HR administrators", { exact: true }),
    ).toBeVisible();

    await page.goto(`/policies/${policy}`);
    const row = page.getByRole("row", { name: /Nia Policy/ });
    await expect(row.getByText("Signed", { exact: true })).toBeVisible();
    await memberPage.close();
  } finally {
    await member.close();
  }
});
