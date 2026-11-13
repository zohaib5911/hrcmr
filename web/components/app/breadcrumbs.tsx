import type { Route } from "next";
import Link from "next/link";

import { cn } from "@/lib/utils";
import type { Crumb } from "@/lib/navigation";

/**
 * "People / Employees" above the page title. The last item is the page you are on.
 * The trail never runs under the toolbar's buttons: below md only the page above this one shows,
 * and any crumb that does not fit is cut short with its full name on hover.
 */
export function Breadcrumbs({ crumbs }: { crumbs: readonly Crumb[] }) {
  if (crumbs.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="text-footnote text-label flex min-w-0 items-center gap-1.5 overflow-hidden whitespace-nowrap">
        {crumbs.map((crumb, index) => {
          const last = index === crumbs.length - 1;
          // Collapsed on phones: the title under the trail already names the current page.
          const collapse = crumbs.length > 1 && index !== crumbs.length - 2;
          return (
            <li
              key={`${crumb.label}-${index}`}
              className={cn("flex min-w-0 items-center gap-1.5", collapse && "max-md:hidden")}
            >
              {crumb.href && !last ? (
                <Link
                  href={crumb.href as Route}
                  title={crumb.label}
                  className="hover:text-label truncate underline-offset-2 hover:underline"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span
                  aria-current={last ? "page" : undefined}
                  title={crumb.label}
                  className="truncate"
                >
                  {crumb.label}
                </span>
              )}
              {last ? null : (
                <span aria-hidden="true" className="shrink-0 max-md:hidden">
                  /
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
