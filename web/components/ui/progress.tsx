import { cn } from "@/lib/utils";

interface ProgressBase {
  /** 0 to 100. Leave out for "working, no estimate". */
  value?: number;
  /** What is progressing: read by screen readers. */
  label: string;
  className?: string;
}

const clamp = (n: number) => Math.min(100, Math.max(0, n));

/**
 * A thin bar. Its fill is an SVG attribute, not an inline `style`: the Content-Security-Policy blocks
 * inline style attributes in server-rendered HTML, so a `style={{ width }}` bar would be empty in
 * production.
 */
export function ProgressBar({ value, label, className }: ProgressBase) {
  const indeterminate = value === undefined;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : Math.round(clamp(value))}
      className={cn("bg-fill-secondary rounded-pill h-1.5 w-full overflow-hidden", className)}
    >
      <svg
        viewBox="0 0 100 6"
        preserveAspectRatio="none"
        className="block h-full w-full"
        aria-hidden="true"
      >
        <rect
          x="0"
          y="0"
          height="6"
          width={indeterminate ? 33 : clamp(value)}
          className={cn(
            "fill-accent motion-small transition-[width]",
            indeterminate && "animate-pulse",
          )}
        />
      </svg>
    </div>
  );
}

const RING = { r: 18, c: 2 * Math.PI * 18 } as const;

export function ProgressRing({
  value,
  label,
  className,
  children,
}: ProgressBase & { children?: React.ReactNode }) {
  const indeterminate = value === undefined;
  const offset = indeterminate ? RING.c * 0.75 : RING.c * (1 - clamp(value) / 100);
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : Math.round(clamp(value))}
      className={cn("relative inline-grid size-12 place-items-center", className)}
    >
      <svg
        viewBox="0 0 44 44"
        className={cn(
          "size-full -rotate-90",
          indeterminate && "animate-spin motion-reduce:animate-pulse",
        )}
        aria-hidden="true"
      >
        <circle
          cx="22"
          cy="22"
          r={RING.r}
          fill="none"
          strokeWidth="4"
          className="stroke-fill-secondary"
        />
        <circle
          cx="22"
          cy="22"
          r={RING.r}
          fill="none"
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={RING.c}
          strokeDashoffset={offset}
          className="stroke-accent motion-small transition-[stroke-dashoffset]"
        />
      </svg>
      {children ? (
        <span className="text-footnote text-label absolute font-medium tabular-nums">
          {children}
        </span>
      ) : null}
    </div>
  );
}
