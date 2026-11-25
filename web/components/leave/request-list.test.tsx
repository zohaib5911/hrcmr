// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { clearApiCache } from "@/lib/api/cache";

const get = vi.fn();
vi.mock("@/components/app/session-context", () => ({ useCan: () => () => true }));
vi.mock("@/lib/auth/request", () => ({
  attempt: async (run: (c: unknown) => Promise<{ data?: unknown; error?: unknown }>) => {
    const r = await run({ GET: get, POST: vi.fn() });
    return r.error ? { ok: false, problem: r.error } : { ok: true, data: r.data };
  },
}));

import { LEAVE_PAGE, RequestList } from "./home";

const request = (n: number) => ({
  id: `r${n}`,
  employee_id: "e1",
  employee_name: `Person ${n}`,
  leave_type_name: "Annual leave",
  start_date: "2026-01-05",
  end_date: "2026-01-05",
  working_days: 1,
  working_dates: ["2026-01-05"],
  status: "pending",
  decision_note: null,
  is_own: false,
});
const all = Array.from({ length: LEAVE_PAGE + 1 }, (_, i) => request(i + 1));

beforeEach(() => {
  clearApiCache();
  get.mockReset();
  get.mockImplementation(async (_path: string, init: { params: { query: { offset: number } } }) => {
    const offset = init.params.query.offset;
    return { data: all.slice(offset, offset + LEAVE_PAGE) };
  });
});

describe("leave request pages (ISS-16)", () => {
  it("reaches the 201st pending approval through the next page", async () => {
    render(<RequestList mode="approvals" />);
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1));
    await userEvent.click(await screen.findByRole("button", { name: "Show more requests" }));
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith("/leave/approvals/own", {
        params: { query: { limit: LEAVE_PAGE, offset: LEAVE_PAGE } },
      }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Show more requests" })).not.toBeInTheDocument(),
    );
  });

  it("asks the server for one person's history instead of filtering a page locally", async () => {
    render(<RequestList employeeId="e9" />);
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith("/leave/requests", {
        params: { query: { limit: LEAVE_PAGE, offset: 0, status: undefined, employee_id: "e9" } },
      }),
    );
  });
});
