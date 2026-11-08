// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { attempt } from "@/lib/auth/request";

import { AnnouncementBanner } from "./announcement-banner";

vi.mock("@/lib/auth/request", () => ({ attempt: vi.fn() }));

const live = {
  id: "a1",
  title: "Planned maintenance",
  body: "The app is read-only on Saturday morning.",
  ends_at: "2026-11-14T10:00:00Z",
};

describe("AnnouncementBanner", () => {
  beforeEach(() => {
    vi.mocked(attempt).mockReset();
  });

  it("shows each live announcement for the company's region", async () => {
    vi.mocked(attempt).mockResolvedValue({ ok: true, data: { items: [live] } });
    render(<AnnouncementBanner />);
    expect(await screen.findByText("Planned maintenance")).toBeTruthy();
    expect(screen.getByText("The app is read-only on Saturday morning.")).toBeTruthy();
  });

  it("shows nothing when there are no live announcements", async () => {
    vi.mocked(attempt).mockResolvedValue({ ok: true, data: { items: [] } });
    render(<AnnouncementBanner />);
    await waitFor(() => expect(attempt).toHaveBeenCalled());
    expect(screen.queryByTestId("announcement-banner")).toBeNull();
  });

  it("shows nothing when the fetch fails, so a notice never blocks the page", async () => {
    vi.mocked(attempt).mockResolvedValue({ ok: false, problem: { status: 500 } } as never);
    render(<AnnouncementBanner />);
    await waitFor(() => expect(attempt).toHaveBeenCalled());
    expect(screen.queryByTestId("announcement-banner")).toBeNull();
  });
});
