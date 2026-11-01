import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

const SIZES = { 16: "size-4", 20: "size-5", 24: "size-6" } as const;

interface IconProps {
  icon: LucideIcon;
  /** 16, 20 or 24 px (plan 5.10). */
  size?: keyof typeof SIZES;
  className?: string;
  /** Only for an icon that carries meaning by itself. Otherwise the icon is hidden from screen readers. */
  label?: string;
}

/** Lucide at a 1.5 px stroke, in the three sizes the design allows. */
export function Icon({ icon: Glyph, size = 20, className, label }: IconProps) {
  return (
    <Glyph
      strokeWidth={1.5}
      className={cn(SIZES[size], "shrink-0", className)}
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
    />
  );
}
