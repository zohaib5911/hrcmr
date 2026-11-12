// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { JobsAdmin } from "./jobs-admin";
const post = vi.fn();
vi.mock("@/lib/auth/request", () => ({
  attempt: async (fn: (c: unknown) => Promise<{ data?: unknown; error?: unknown }>) => {
    const r = await fn({ POST: post });
    return r.error ? { ok: false, problem: r.error } : { ok: true, data: r.data };
  },
}));
const failure = {
  id: "f1",
  created_at: "2026-11-01T10:00:00Z",
  job: "rtw_status_daily",
  detail: { kind: "TimeoutError" },
};
const props = {
  queue: { waiting: 3 },
  failures: { items: [failure, { ...failure, id: "f2", job: "send_mail" }], total: 51 },
  offset: 0,
};
beforeEach(() => post.mockResolvedValue({ data: { job: failure.job, job_id: "queued" } }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it("requires a reason, confirms and sends only one allow-listed run", async () => {
  render(<JobsAdmin {...props} />);
  expect(screen.getByText("Waiting in queue: 3")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Run again" })).toHaveLength(1);
  expect(screen.getByRole("button", { name: "Run again" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Reason for running again"), "Investigate failure");
  await userEvent.click(screen.getByRole("button", { name: "Run again" }));
  expect(post).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Queue run" }));
  expect(await screen.findByText("rtw_status_daily queued for another run.")).toBeInTheDocument();
  expect(post).toHaveBeenCalledExactlyOnceWith("/platform/jobs/failures/{failure_id}/rerun", {
    params: { path: { failure_id: "f1" } },
    body: { reason: "Investigate failure" },
  });
  expect(screen.getByRole("link", { name: "Next" })).toHaveAttribute("href", "/jobs?offset=50");
});
it("shows the API refusal without reporting success", async () => {
  post.mockResolvedValue({
    error: { code: "NOT_RERUNNABLE", message: "This job cannot be run again." },
  });
  render(<JobsAdmin {...props} />);
  await userEvent.type(screen.getByLabelText("Reason for running again"), "Investigate failure");
  await userEvent.click(screen.getByRole("button", { name: "Run again" }));
  await userEvent.click(screen.getByRole("button", { name: "Queue run" }));
  expect(await screen.findByText("This job cannot be run again.")).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByText("Job queued")).not.toBeInTheDocument());
});
it("shows empty and unavailable data states", () => {
  const { rerender } = render(
    <JobsAdmin queue={{ waiting: 0 }} failures={{ items: [], total: 0 }} offset={0} />,
  );
  expect(screen.getByText("No failed jobs.")).toBeInTheDocument();
  rerender(<JobsAdmin queue={null} failures={null} offset={0} />);
  expect(screen.getByText("Could not load queue")).toBeInTheDocument();
  expect(screen.getByText("Could not load failures")).toBeInTheDocument();
});
