// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";

const get = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));
vi.mock("@/components/app/session-context", () => ({ useCan: () => () => true }));
vi.mock("@/lib/auth/request", () => ({
  attempt: async (run: (c: unknown) => Promise<{ data?: unknown; error?: unknown }>) => {
    const r = await run({ GET: get, POST: vi.fn(), PATCH: vi.fn() });
    return r.error ? { ok: false, problem: r.error } : { ok: true, data: r.data };
  },
}));

import { EmploymentTab, type EmploymentData } from "./employment-tab";

const employment = {
  hire_date: "2024-01-01",
  assignments: [
    {
      id: "a1",
      employment_type: "full_time",
      effective_from: "2024-01-01",
      ended_at: null,
      reporting_authority_employee_id: "boss",
      reporting_authority: "Bea Boss",
      leave_sanctioning_employee_id: null,
      leave_sanctioning_authority: null,
    },
  ],
  previous_employment: null,
  memberships: [],
  responsibilities: [],
  education: [],
  training: [],
} as unknown as EmploymentData;

beforeEach(() => {
  get.mockReset();
  get.mockImplementation(async (path: string) =>
    path === "/employees"
      ? {
          data: {
            employees: [
              { id: "self", first_name: "Sam", last_name: "Self", employee_number: "E1" },
              { id: "p2", first_name: "Pat", last_name: "Lead", employee_number: "E2" },
            ],
          },
        }
      : { data: [] },
  );
});

describe("the employment tab's authority pickers (ISS-17)", () => {
  it("loads nothing for the read-only view, then searches when the editor is open", async () => {
    render(
      <ToastProvider>
        <EmploymentTab id="self" employment={employment} />
      </ToastProvider>,
    );
    expect(screen.getAllByText("Bea Boss").length).toBeGreaterThan(0);
    const lookups = ["/employees", "/departments", "/designations", "/locations"];
    const called = () => get.mock.calls.map(([path]) => path as string);
    expect(called().filter((path) => lookups.includes(path))).toEqual([]);

    await userEvent.click(screen.getByRole("button", { name: "Change role" }));
    await waitFor(() => expect(get).toHaveBeenCalledWith("/departments"));
    expect(called()).not.toContain("/employees");
    const picker = screen.getByRole("combobox", { name: "Reporting Authority" });
    expect(picker).toHaveValue("Bea Boss"); // the current choice, by id, without a directory load

    await userEvent.clear(picker);
    await userEvent.type(picker, "Pat");
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(
        "/employees",
        expect.objectContaining({
          params: { query: { q: "Pat" } },
        }),
      ),
    );
    expect(await screen.findByRole("option", { name: /Pat Lead/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Sam Self/ })).not.toBeInTheDocument();
  });
});
