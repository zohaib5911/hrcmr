import type { ReactNode } from "react";
import { vi } from "vitest";

/**
 * Stand-ins for the parts of Next.js that need a running app: the current address, the router and
 * `<Link>`. Call `mockNext("/employees")` before importing the component, and read `router` after.
 */
export const router = {
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
};

export function mockNext(pathname: string) {
  vi.doMock("next/navigation", () => ({
    usePathname: () => pathname,
    useRouter: () => router,
    notFound: () => {
      throw new Error("NEXT_NOT_FOUND");
    },
  }));
  vi.doMock("next/link", () => ({
    default: ({
      href,
      children,
      ...rest
    }: { href: string; children: ReactNode } & Record<string, unknown>) => (
      <a href={href} {...rest}>
        {children}
      </a>
    ),
  }));
}
