import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/lib/api/client";

import { allEmployees, type EmployeeRow } from "./list";

const person = (id: string) => ({ id, first_name: id }) as unknown as EmployeeRow;

function fakeClient(
  pages: Record<number, { employees: EmployeeRow[]; next_offset: number | null }>,
) {
  const GET = vi.fn(async (_path: string, init: { params: { query: { offset: number } } }) => {
    const page = pages[init.params.query.offset];
    return page
      ? { data: { ...page, total: 3 }, response: new Response(null, { status: 200 }) }
      : { error: { error: { code: "X" } }, response: new Response(null, { status: 500 }) };
  });
  return { client: { GET } as unknown as ApiClient, GET };
}

describe("allEmployees", () => {
  it("follows next_offset until the last page, so nobody is left out", async () => {
    const { client, GET } = fakeClient({
      0: { employees: [person("a"), person("b")], next_offset: 2 },
      2: { employees: [person("c")], next_offset: null },
    });
    const result = await allEmployees(client, { archived: true });
    expect(result.data?.employees.map((e) => e.id)).toEqual(["a", "b", "c"]);
    expect(GET.mock.calls.map((call) => call[1].params.query)).toEqual([
      { archived: true, offset: 0 },
      { archived: true, offset: 2 },
    ]);
  });

  it("returns a failed page as it came", async () => {
    const { client } = fakeClient({ 0: { employees: [person("a")], next_offset: 5 } });
    const result = await allEmployees(client);
    expect(result.data).toBeUndefined();
    expect(result.response.status).toBe(500);
  });

  it("stops on an offset that does not move forward", async () => {
    const { client, GET } = fakeClient({ 0: { employees: [person("a")], next_offset: 0 } });
    const result = await allEmployees(client);
    expect(result.data?.employees).toHaveLength(1);
    expect(GET).toHaveBeenCalledTimes(1);
  });
});
