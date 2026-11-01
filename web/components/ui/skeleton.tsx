import { cn } from "@/lib/utils";

/** One quiet placeholder block. Decorative: the group that contains it announces "Loading". */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("skeleton", className)} />;
}

function Group({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div role="status" aria-busy="true" className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

/** Lines of text, the last one shorter. */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <Group label="Loading" className={cn("flex flex-col gap-2", className)}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton
          key={i}
          className={cn("h-4", i === lines - 1 && lines > 1 ? "w-2/3" : "w-full")}
        />
      ))}
    </Group>
  );
}

/** Same footprint as an Avatar and two lines: a person row. */
export function SkeletonPerson({ className }: { className?: string }) {
  return (
    <Group label="Loading" className={cn("flex items-center gap-3", className)}>
      <Skeleton className="rounded-pill size-10 shrink-0" />
      <div className="flex flex-1 flex-col gap-2">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </Group>
  );
}

/** Same footprint as a KpiCard. */
export function SkeletonKpi({ className }: { className?: string }) {
  return (
    <Group
      label="Loading"
      className={cn("bg-elevated rounded-card shadow-e1 flex flex-col gap-3 p-5", className)}
    >
      <Skeleton className="h-3 w-1/3" />
      <Skeleton className="h-9 w-1/2" />
      <Skeleton className="h-3 w-2/3" />
    </Group>
  );
}

/** Same footprint as a Card with a header and body text. */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <Group
      label="Loading"
      className={cn("bg-elevated rounded-card shadow-e1 flex flex-col gap-4 p-5", className)}
    >
      <Skeleton className="h-5 w-1/3" />
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    </Group>
  );
}

/** Rows and columns, matching DataTable's row height so nothing shifts when the data arrives. */
export function SkeletonTable({
  rows = 5,
  columns = 4,
  className,
}: {
  rows?: number;
  columns?: number;
  className?: string;
}) {
  return (
    <Group
      label="Loading"
      className={cn(
        "bg-elevated rounded-card shadow-e1 divide-separator divide-y overflow-hidden",
        className,
      )}
    >
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className="flex h-12 items-center gap-6 px-4">
          {Array.from({ length: columns }, (_, col) => (
            <Skeleton key={col} className={cn("h-4", col === 0 ? "w-1/4" : "w-1/6")} />
          ))}
        </div>
      ))}
    </Group>
  );
}
