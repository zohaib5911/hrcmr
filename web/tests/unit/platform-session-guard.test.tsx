import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
let hasCookie = true;

vi.mock("next/navigation", () => ({
  redirect: (to: string) => {
    throw new Error(`REDIRECT ${to}`);
  },
}));
vi.mock("@/lib/platform/guard", async (orig) => ({
  ...(await orig<typeof import("@/lib/platform/guard")>()),
  platformApi: async () => (hasCookie ? { GET: get } : null),
}));
vi.mock("next/headers", () => ({ cookies: async () => ({}) }));
vi.mock("@/components/platform/queues-admin", () => ({ QueuesAdmin: () => null }));
vi.mock("@/components/platform/contact-admin", () => ({ ContactAdmin: () => null }));
vi.mock("@/components/platform/users-admin", () => ({ UsersAdmin: () => null }));
vi.mock("@/components/platform/subscriptions-admin", () => ({ SubscriptionsAdmin: () => null }));

import ContactPage from "@/app/(admin)/platform/contact/page";
import QueuesPage from "@/app/(admin)/platform/queues/page";
import SubscriptionsPage from "@/app/(admin)/platform/subscriptions/page";
import UsersPage from "@/app/(admin)/platform/users/page";

const pages = [
  ["/queues", QueuesPage],
  ["/contact", ContactPage],
  ["/users", UsersPage],
  ["/subscriptions", SubscriptionsPage],
] as const;

beforeEach(() => {
  hasCookie = true;
  get.mockReset();
});

describe.each(pages)("%s page", (path, Page) => {
  const start = `REDIRECT /session?next=${encodeURIComponent(path)}`;

  it("goes to the start page without a platform cookie", async () => {
    hasCookie = false;
    await expect(Page()).rejects.toThrow(start);
    expect(get).not.toHaveBeenCalled();
  });

  it.each([401, 403])("goes to the start page when the API answers %i", async (status) => {
    get.mockResolvedValue({ response: { status } });
    await expect(Page()).rejects.toThrow(start);
  });

  it("validates the session through an audited platform read and renders", async () => {
    get.mockResolvedValue({ data: { owner: false }, response: { status: 200 } });
    await expect(Page()).resolves.toBeTruthy();
    expect(get).toHaveBeenCalledWith("/platform/context");
  });
});
