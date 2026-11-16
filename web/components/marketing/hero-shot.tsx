import Image from "next/image";

import { cn } from "@/lib/utils";

import darkShot from "@/public/marketing/dashboard-dark.webp";
import lightShot from "@/public/marketing/dashboard-light.webp";

/**
 * The real dashboard in a glass window (U6.1.8). Both themes are drawn and CSS shows the one that
 * matches, so the picture follows the visitor's theme with no script. Fixed dimensions: nothing
 * shifts while it loads. Captured from the app (docs/screenshots/phase-25/u614-cards).
 */
export function HeroShot({ className }: { className?: string }) {
  const alt =
    "The dashboard: a set-up checklist, headline numbers for employees, leave and Right to Work, and cards for approvals, learning and recruitment.";
  const shared = {
    sizes: "(min-width: 1152px) 1088px, calc(100vw - 2rem)",
    className: "rounded-control h-auto w-full",
  } as const;
  return (
    <figure className={cn("material-glass-thick rounded-sheet mx-auto max-w-5xl p-2", className)}>
      <div aria-hidden className="flex gap-1.5 px-2 pt-1 pb-2">
        <span className="bg-danger-fill size-2.5 rounded-full opacity-70" />
        <span className="bg-warning-fill size-2.5 rounded-full opacity-70" />
        <span className="bg-success-fill size-2.5 rounded-full opacity-70" />
      </div>
      {/* Only the light picture is preloaded at high priority: two would compete for the first
          bytes on a phone. The dark one still loads at once, at low priority. */}
      <Image
        src={lightShot}
        alt={alt}
        {...shared}
        preload
        loading="eager"
        fetchPriority="high"
        className={cn(shared.className, "dark:hidden")}
      />
      <Image
        src={darkShot}
        alt={alt}
        {...shared}
        loading="eager"
        fetchPriority="low"
        className={cn(shared.className, "hidden dark:block")}
      />
    </figure>
  );
}
