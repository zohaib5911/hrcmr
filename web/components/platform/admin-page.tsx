import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const WIDTH = { wide: "max-w-6xl", form: "max-w-4xl", narrow: "max-w-xl" } as const;

/**
 * The one frame for every platform admin page (design audit row F): the grouped canvas, the same
 * 16 px phone / 32 px desktop gutters, and a centred column. The red platform bar sits above it in the
 * admin layout. Inside, each page starts with a PageHeader (its only h1).
 */
export function AdminPage({
  children,
  width = "wide",
  className,
}: {
  children: ReactNode;
  width?: keyof typeof WIDTH;
  className?: string;
}) {
  return (
    <main className="bg-grouped min-h-dvh px-4 pt-6 pb-16 sm:px-8 sm:pt-8">
      <div className={cn("mx-auto flex w-full flex-col", WIDTH[width], className)}>{children}</div>
    </main>
  );
}

/** An admin page while it loads: the same frame, a title placeholder and rows, announced by name. */
export function AdminPageLoading({
  label,
  width = "wide",
}: {
  label: string;
  width?: keyof typeof WIDTH;
}) {
  return (
    <AdminPage width={width}>
      <div role="status" aria-busy="true">
        <span className="sr-only">{label}</span>
        <div className="flex flex-col gap-2 pb-6">
          <Skeleton className="h-10 w-56" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </div>
        <div className="bg-elevated rounded-card shadow-e1 grouped-rows overflow-hidden">
          {Array.from({ length: 6 }, (_, row) => (
            <div key={row} className="flex h-13 items-center gap-6 px-4">
              <Skeleton className="h-4 w-1/3 sm:w-1/4" />
              <Skeleton className="hidden h-4 w-1/6 sm:block" />
              <Skeleton className="h-4 w-1/6" />
            </div>
          ))}
        </div>
      </div>
    </AdminPage>
  );
}
