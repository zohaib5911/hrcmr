"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { routeSkeleton, type RouteSkeleton } from "@/lib/ui/route-skeleton";
import { cn } from "@/lib/utils";

import { isShellReady } from "./shell-ready";
import { WorkspaceSplash } from "./workspace-splash";

/** The Large Title, its sentence and one action: the same footprint as PageHeader. */
function HeaderSkeleton() {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 pb-6">
      <div className="flex min-w-0 flex-col gap-2">
        <Skeleton className="h-10 w-48 sm:w-64" />
        <Skeleton className="h-4 w-64 max-w-full sm:w-96" />
      </div>
      <Skeleton className="rounded-pill h-11 w-32" />
    </div>
  );
}

const surface = "bg-elevated rounded-card shadow-e1";

function ListBody() {
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Skeleton className="rounded-pill h-11 w-full sm:w-72" />
        <Skeleton className="rounded-pill h-9 w-40" />
      </div>
      <div className={cn(surface, "grouped-rows overflow-hidden")}>
        {Array.from({ length: 6 }, (_, row) => (
          <div key={row} className="flex h-13 items-center gap-6 px-4">
            <Skeleton className="rounded-pill size-8 shrink-0" />
            <Skeleton className="h-4 w-1/3 sm:w-1/4" />
            <Skeleton className="hidden h-4 w-1/6 sm:block" />
            <Skeleton className="hidden h-4 w-1/6 md:block" />
          </div>
        ))}
      </div>
    </>
  );
}

function CardBody() {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className={cn(surface, "flex flex-col gap-3 p-5")}>
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-9 w-1/2" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 2 }, (_, i) => (
          <div key={i} className={cn(surface, "flex flex-col gap-4 p-5")}>
            <Skeleton className="h-5 w-1/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ))}
      </div>
    </>
  );
}

function FormBody() {
  return (
    <div className="flex max-w-2xl flex-col gap-6">
      {[4, 3].map((rows, group) => (
        <div key={group} className="flex flex-col gap-2">
          <Skeleton className="mx-4 h-3 w-24" />
          <div className={cn(surface, "grouped-rows overflow-hidden")}>
            {Array.from({ length: rows }, (_, row) => (
              <div key={row} className="flex min-h-11 items-center justify-between gap-4 px-4 py-3">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-4 w-1/4" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function CalendarBody() {
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Skeleton className="rounded-pill h-9 w-56" />
        <Skeleton className="rounded-pill h-9 w-32" />
      </div>
      <div className={cn(surface, "grid grid-cols-7 gap-px overflow-hidden p-px")}>
        {Array.from({ length: 35 }, (_, day) => (
          <div key={day} className="flex h-16 flex-col gap-2 p-2 sm:h-24">
            <Skeleton className="h-3 w-5" />
            {day % 3 === 0 ? <Skeleton className="hidden h-4 w-full sm:block" /> : null}
          </div>
        ))}
      </div>
    </>
  );
}

const BODY: Record<RouteSkeleton, () => React.ReactNode> = {
  list: ListBody,
  card: CardBody,
  form: FormBody,
  calendar: CalendarBody,
};

/** The placeholder for one route family, inside the shell's content frame. */
export function RouteSkeletonView({ family }: { family: RouteSkeleton }) {
  const Body = BODY[family];
  return (
    <div role="status" aria-busy="true" data-skeleton={family}>
      <span className="sr-only">Loading</span>
      <HeaderSkeleton />
      <Body />
    </div>
  );
}

/**
 * What a signed-in page shows while it loads (design audit row B). The first load after sign-in keeps
 * the calm workspace splash; once the shell is on screen, moving between pages keeps the sidebar and
 * toolbar and shows a skeleton shaped like the page that is coming.
 */
export function RouteLoading() {
  const pathname = usePathname();
  const [splash] = useState(() => !isShellReady());
  if (splash) return <WorkspaceSplash />;
  return <RouteSkeletonView family={routeSkeleton(pathname ?? "/")} />;
}
