/* eslint-disable @next/next/no-img-element -- Local, fixed-size SVG artwork; CSS selects the theme before first paint. */
import { brand } from "@brand";

import { cn } from "@/lib/utils";

/** The owner's unmodified artwork, with dimensions reserved before the image loads. */
export function BrandLogo({
  variant = "lockup",
  className,
}: {
  variant?: "lockup" | "mark";
  className?: string;
}) {
  const mark = variant === "mark";
  const width = mark ? 32 : 135;
  const height = 32;
  const light = mark ? brand.logo.markSmall : brand.logo.fullLockup;
  const dark = mark ? brand.logo.markSmall : brand.logo.fullLockupDark;
  return (
    <span className={cn("inline-flex shrink-0 align-middle", className)}>
      <img
        src={light}
        width={width}
        height={height}
        alt={brand.name}
        className="block dark:hidden"
      />
      <img
        src={dark}
        width={width}
        height={height}
        alt={brand.name}
        className="hidden dark:block"
      />
    </span>
  );
}
