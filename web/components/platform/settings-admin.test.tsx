// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, it, expect, beforeEach } from "vitest";
import { SettingsAdmin, type SettingsData } from "./settings-admin";
const { attempt } = vi.hoisted(() => ({ attempt: vi.fn() }));
vi.mock("@/lib/auth/request", () => ({ attempt }));
const empty: SettingsData = {
  owner: true,
  terms: { items: [], total: 0 },
  flags: { items: [], total: 0 },
  announcements: { items: [], total: 0 },
};
beforeEach(() => {
  attempt.mockReset();
});
it("shows empty states and hides publishing for support", () => {
  render(<SettingsAdmin {...empty} owner={false} />);
  expect(screen.getByText("No terms versions yet.")).toBeInTheDocument();
  expect(screen.getByText("No feature flags yet.")).toBeInTheDocument();
  expect(screen.getByText("No announcements yet.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Publish new version" })).not.toBeInTheDocument();
});
it("shows independent load errors", () => {
  render(<SettingsAdmin {...empty} terms={null} flags={null} announcements={null} />);
  expect(screen.getAllByRole("alert")).toHaveLength(3);
});
it("requires reason and a second confirmation to publish terms", async () => {
  const user = userEvent.setup();
  const post = vi.fn().mockResolvedValue({});
  attempt.mockImplementation(async (fn) => {
    await fn({ POST: post });
    return {
      ok: true,
      data: {
        id: "t",
        version: "v2",
        url: "/terms",
        published_at: "2026-11-12T00:00:00Z",
        current: true,
      },
    };
  });
  render(<SettingsAdmin {...empty} />);
  expect(screen.getByRole("button", { name: "Publish new version" })).toBeDisabled();
  await user.type(screen.getByLabelText("Reason for change"), "Legal review");
  await user.type(screen.getByLabelText("Version"), "v2");
  await user.type(screen.getByLabelText("Terms URL"), "/terms");
  await user.click(screen.getByRole("button", { name: "Publish new version" }));
  expect(post).not.toHaveBeenCalled();
  const dialog = screen.getByRole("alertdialog");
  expect(dialog).toHaveTextContent("Every user must accept again");
  await user.click(within(dialog).getByRole("button", { name: "Publish terms" }));
  expect(post).toHaveBeenCalledExactlyOnceWith("/platform/terms-versions", {
    body: { version: "v2", url: "/terms", reason: "Legal review" },
  });
});
it("sends the flag value and reason", async () => {
  const user = userEvent.setup();
  const put = vi.fn().mockResolvedValue({});
  const flag = {
    key: "new_feature",
    enabled: false,
    description: "New feature",
    updated_at: "2026-11-12T00:00:00Z",
  };
  attempt.mockImplementation(async (fn) => {
    await fn({ PUT: put });
    return { ok: true, data: { ...flag, enabled: true } };
  });
  render(<SettingsAdmin {...empty} flags={{ items: [flag], total: 1 }} />);
  expect(screen.getByRole("switch")).toBeDisabled();
  await user.type(screen.getByLabelText("Reason for change"), "Launch feature");
  await user.click(screen.getByRole("switch"));
  expect(put).toHaveBeenCalledExactlyOnceWith("/platform/feature-flags/{key}", {
    params: { path: { key: flag.key } },
    body: { enabled: true, reason: "Launch feature" },
  });
  expect(screen.getByRole("switch")).toBeChecked();
});
it("creates a regional announcement and ends it with confirmation", async () => {
  const user = userEvent.setup();
  const post = vi.fn().mockResolvedValue({});
  const a = {
    id: "a",
    title: "Maintenance",
    body: "Service notice",
    region: "uk",
    starts_at: "2026-11-12T10:00:00Z",
    ends_at: "2026-11-13T10:00:00Z",
    ended_at: null,
    status: "live",
  };
  attempt
    .mockImplementationOnce(async (fn) => {
      await fn({ POST: post });
      return { ok: true, data: a };
    })
    .mockImplementationOnce(async (fn) => {
      await fn({ POST: post });
      return { ok: true, data: { ...a, status: "ended" } };
    });
  render(<SettingsAdmin {...empty} />);
  await user.type(screen.getByLabelText("Reason for change"), "Scheduled maintenance");
  await user.type(screen.getByLabelText("Announcement title"), a.title);
  await user.type(screen.getByLabelText("Message"), a.body);
  await user.type(screen.getByLabelText("Start date"), "12 Nov 2026");
  await user.type(screen.getByLabelText("Start time"), "10:00");
  await user.type(screen.getByLabelText("End date"), "13 Nov 2026");
  await user.type(screen.getByLabelText("End time"), "10:00");
  await user.tab();
  await user.click(screen.getByRole("button", { name: "Create announcement" }));
  expect(post).toHaveBeenCalledWith("/platform/announcements", {
    body: expect.objectContaining({
      title: a.title,
      body: a.body,
      region: "uk",
      reason: "Scheduled maintenance",
      starts_at: new Date("2026-11-12T10:00").toISOString(),
    }),
  });
  await user.click(screen.getByRole("button", { name: "End now" }));
  await user.click(
    within(screen.getByRole("alertdialog")).getByRole("button", { name: "End announcement" }),
  );
  expect(post).toHaveBeenLastCalledWith("/platform/announcements/{announcement_id}/end", {
    params: { path: { announcement_id: "a" } },
    body: { reason: "Scheduled maintenance" },
  });
  expect(screen.queryByRole("button", { name: "End now" })).not.toBeInTheDocument();
});
it("shows API refusals", async () => {
  const user = userEvent.setup();
  attempt.mockResolvedValue({
    ok: false,
    problem: { code: "VERSION_EXISTS", message: "Choose a new version." },
  });
  render(<SettingsAdmin {...empty} />);
  await user.type(screen.getByLabelText("Reason for change"), "Legal review");
  await user.type(screen.getByLabelText("Version"), "v2");
  await user.type(screen.getByLabelText("Terms URL"), "/terms");
  await user.click(screen.getByRole("button", { name: "Publish new version" }));
  await user.click(
    within(screen.getByRole("alertdialog")).getByRole("button", { name: "Publish terms" }),
  );
  expect(screen.getByRole("alert")).toHaveTextContent("Choose a new version.");
});
