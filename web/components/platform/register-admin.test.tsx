// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { components } from "@/lib/api/client";
import { RegisterAdmin } from "./register-admin";

const post = vi.fn();
vi.mock("@/lib/auth/request", () => ({
  attempt: async (fn: (c: unknown) => Promise<{ data?: unknown; error?: unknown }>) => {
    const r = await fn({ POST: post });
    return r.error ? { ok: false, problem: r.error } : { ok: true, data: r.data };
  },
}));
const status: components["schemas"]["RegisterStatusOut"] = {
  last_publication: {
    id: "pub1",
    published_on: "2026-11-11",
    fetched_at: "2026-11-11T10:20:00Z",
    source_url: "https://www.gov.uk/register.csv",
    row_count: 7,
    status: "complete",
  },
  current_sponsors: 5,
  total_sponsors: 9,
  errors: [
    {
      id: "err1",
      created_at: "2026-11-10T12:00:00Z",
      job: "register_ingest",
      detail: { kind: "TimeoutError" },
    },
  ],
};
beforeEach(() => {
  post.mockResolvedValue({ data: { job: "register_ingest", job_id: "queued" } });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
async function confirmRun() {
  await userEvent.type(
    screen.getByLabelText("Reason for rerunning import"),
    "  Source recovered  ",
  );
  await userEvent.click(screen.getByRole("button", { name: "Rerun import" }));
  expect(post).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Queue import" }));
}
it("renders publication, sponsor counts and recent failure details", () => {
  render(<RegisterAdmin status={status} />);
  for (const text of [
    "5",
    "9",
    "7",
    "11 Nov 2026",
    "2026-11-11T10:20:00Z",
    "complete",
    "2026-11-10T12:00:00Z",
  ])
    expect(screen.getByText(text)).toBeInTheDocument();
  expect(
    screen.getByRole("table", { name: "Register import failures (latest 20)" }),
  ).toHaveTextContent("TimeoutError");
});
it("shows empty status and still allows the first import", () => {
  render(
    <RegisterAdmin
      status={{ last_publication: null, current_sponsors: 0, total_sponsors: 0, errors: [] }}
    />,
  );
  expect(screen.getByText("No register publications imported yet.")).toBeInTheDocument();
  expect(screen.getByText("No recent import errors.")).toBeInTheDocument();
  expect(screen.getByLabelText("Reason for rerunning import")).toBeEnabled();
});
it("fails closed when status is unavailable", () => {
  render(<RegisterAdmin status={null} />);
  expect(screen.getByText("Could not load register status")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Rerun import" })).toBeDisabled();
  expect(screen.getByLabelText("Reason for rerunning import")).toBeDisabled();
});
it("requires five trimmed characters then confirms and queues only the safe endpoint", async () => {
  render(<RegisterAdmin status={status} />);
  const input = screen.getByLabelText("Reason for rerunning import");
  const button = screen.getByRole("button", { name: "Rerun import" });
  expect(input).toHaveAttribute("maxlength", "500");
  expect(button).toBeDisabled();
  await userEvent.type(input, "    abcd    ");
  expect(button).toBeDisabled();
  await userEvent.clear(input);
  await confirmRun();
  expect(await screen.findByText("Import queued")).toBeInTheDocument();
  expect(post).toHaveBeenCalledExactlyOnceWith("/platform/register/run", {
    body: { reason: "Source recovered" },
  });
});
it.each(["UNAUTHENTICATED", "FORBIDDEN"])(
  "disables reruns after %s without reporting success",
  async (code) => {
    post.mockResolvedValue({ error: { code, message: "Platform access required." } });
    render(<RegisterAdmin status={status} />);
    await confirmRun();
    expect(await screen.findByText("Platform access required.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start a new platform session" })).toHaveAttribute(
      "href",
      "/session?next=%2Fregister",
    );
    expect(screen.getByRole("button", { name: "Rerun import" })).toBeDisabled();
    expect(screen.queryByText("Import queued")).not.toBeInTheDocument();
  },
);
it("shows recoverable queue errors and permits another attempt", async () => {
  post.mockResolvedValue({ error: { code: "NETWORK", message: "Could not reach the server." } });
  render(<RegisterAdmin status={status} />);
  await confirmRun();
  expect(await screen.findByText("Could not reach the server.")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Rerun import" })).toBeEnabled());
  expect(screen.queryByText("Import queued")).not.toBeInTheDocument();
});
it("disables duplicate reruns while the queue request is pending", async () => {
  let finish!: (value: unknown) => void;
  post.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  render(<RegisterAdmin status={status} />);
  await confirmRun();
  expect(screen.getByRole("button", { name: "Queue import" })).toBeDisabled();
  expect(screen.getByLabelText("Reason for rerunning import")).toBeDisabled();
  finish({ data: { job: "register_ingest", job_id: "queued" } });
  expect(await screen.findByText("Import queued")).toBeInTheDocument();
  expect(post).toHaveBeenCalledTimes(1);
});
