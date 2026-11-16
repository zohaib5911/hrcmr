"use client";

import { animate, useInView, useReducedMotion } from "motion/react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, type ComponentProps } from "react";

import { countUpSeconds } from "@/lib/motion";
import { cn } from "@/lib/utils";

import { Card } from "./card";
import { Icon } from "./icon";

interface KpiCardProps {
  label: string;
  value: number;
  /** How to write the number. Defaults to thousands separators ("1,284"). */
  format?: (value: number) => string;
  subLabel?: string;
  /** A small line icon beside the label. */
  icon?: LucideIcon;
  /** One short line under the number, so a 0 is never the only thing on the card. */
  status?: { text: string; tone?: "neutral" | "success" | "warning" | "danger" };
  /** A short series for the sparkline. Say what it shows in `trendLabel`. */
  trend?: readonly number[];
  trendLabel?: string;
  link?: { href: ComponentProps<typeof Link>["href"]; label: string };
  className?: string;
}

const STATUS_TONE = {
  neutral: "text-label-secondary",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
} as const;

const defaultFormat = (value: number) => value.toLocaleString("en-GB");

function Sparkline({ values }: { values: readonly number[] }) {
  const min = Math.min(...values);
  const range = Math.max(...values) - min || 1;
  const points = values
    .map((v, i) => `${(i / Math.max(values.length - 1, 1)) * 100},${22 - ((v - min) / range) * 20}`)
    .join(" ");
  return (
    <svg
      viewBox="0 0 100 24"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="text-accent-text h-6 w-full"
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

/** A label, one big number, and what it means. The number counts up once, the first time it is seen. */
export function KpiCard({
  label,
  value,
  format = defaultFormat,
  subLabel,
  icon,
  status,
  trend,
  trendLabel,
  link,
  className,
}: KpiCardProps) {
  const number = useRef<HTMLSpanElement>(null);
  const seen = useInView(number, { once: true, amount: 0.6 });
  const reduced = useReducedMotion();
  const formatRef = useRef(format);
  useEffect(() => {
    formatRef.current = format;
  });

  useEffect(() => {
    const node = number.current;
    if (!seen || reduced || !node) return;
    const controls = animate(0, value, {
      duration: countUpSeconds(false),
      ease: "easeOut",
      onUpdate: (current) => {
        node.textContent = formatRef.current(Math.round(current));
      },
      onComplete: () => {
        node.textContent = formatRef.current(value);
      },
    });
    return () => controls.stop();
  }, [seen, reduced, value]);

  return (
    <Card variant="glass" className={cn("flex flex-col gap-1 p-5", className)}>
      <p className="text-subheadline text-label-secondary flex items-center gap-2">
        {icon ? <Icon icon={icon} size={16} /> : null}
        {label}
      </p>
      <p className="text-large-title text-label tabular-nums">
        <span ref={number}>{format(value)}</span>
      </p>
      {subLabel ? <p className="text-subheadline text-label-secondary">{subLabel}</p> : null}
      {status ? (
        <p className={cn("text-footnote font-medium", STATUS_TONE[status.tone ?? "neutral"])}>
          {status.text}
        </p>
      ) : null}
      {trend && trend.length > 1 ? (
        <div className="mt-2">
          <Sparkline values={trend} />
          {trendLabel ? <p className="sr-only">{trendLabel}</p> : null}
        </div>
      ) : null}
      {link ? (
        <Link
          href={link.href}
          className="text-callout text-accent-text mt-2 self-start font-medium underline-offset-2 hover:underline"
        >
          {link.label}
        </Link>
      ) : null}
    </Card>
  );
}
