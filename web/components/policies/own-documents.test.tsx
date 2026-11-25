// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { OwnPolicy } from "./labels";

const get = vi.fn();
vi.mock("@/components/app/session-context", () => ({ useCan: () => () => true }));
vi.mock("@/lib/auth/request", () => ({
  baseUrl: () => "http://api.test",
  attempt: async (run: (c: unknown) => Promise<{ data?: unknown; error?: unknown }>) => {
    const r = await run({ GET: get });
    return r.error ? { ok: false, problem: r.error } : { ok: true, data: r.data };
  },
}));

import { OwnPolicies } from "./own-documents";

const policy = (n: number): OwnPolicy => ({
  id: `p${n}`,
  title: `Policy ${n}`,
  version: 1,
  confirmation_mode: "accept",
  due_on: "2026-12-01",
  status: "pending",
  accepted_at: null,
  file_mime: "application/msword",
  archived: false,
});
const all = Array.from({ length: 51 }, (_, i) => policy(i + 1));

beforeEach(() => {
  get.mockReset();
  get.mockImplementation(
    async (
      path: string,
      init: { params: { query?: { offset?: number }; path?: { policy_id: string } } },
    ) => {
      if (path === "/policies/own/{policy_id}") {
        const found = all.find((item) => item.id === init.params.path?.policy_id);
        return found ? { data: found } : { error: { code: "NOT_FOUND", message: "Not found" } };
      }
      const offset = init.params.query?.offset ?? 0;
      return { data: { items: all.slice(offset, offset + 50), total: all.length } };
    },
  );
});

describe("My documents policies (ISS-14)", () => {
  it("reaches the 51st assignment through the next page", async () => {
    render(<OwnPolicies />);
    expect(await screen.findByText("Policy 50")).toBeInTheDocument();
    expect(screen.queryByText("Policy 51")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Show more \(1 more\)/ }));
    expect(await screen.findByText("Policy 51")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show more/ })).not.toBeInTheDocument();
  });

  it("opens the policy a notice links to, even when it is not on the first page", async () => {
    render(<OwnPolicies selectedId="p51" />);
    expect(await screen.findByText("Policy 51")).toBeInTheDocument();
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith("/policies/own/{policy_id}", {
        params: { path: { policy_id: "p51" } },
      }),
    );
  });

  it("says so when the linked policy is not the person's", async () => {
    render(<OwnPolicies selectedId="someone-elses" />);
    expect(await screen.findByText("That policy is not available to you.")).toBeInTheDocument();
  });
});
