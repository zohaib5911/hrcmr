import { cn } from "@/lib/utils";

/**
 * The soft colour behind the glass (U6.1.2): two wide, faint glows in the accent and a neighbouring
 * hue, strongest in the top corners and gone by 40% of the height, so tables and forms stay on calm
 * ground. CSS only. The parent must be `isolate` (or another stacking context), or the page
 * background paints over it.
 *
 * `page` stays put while the page scrolls (the app and sign-in frames); `section` fills one section
 * (a marketing hero), which must also be `relative overflow-hidden`.
 */
export function AmbientBackdrop({ scope = "page" }: { scope?: "page" | "section" }) {
  return (
    <div
      aria-hidden
      data-ambient-backdrop={scope}
      className={cn("ambient-backdrop", scope === "page" ? "fixed" : "absolute")}
    />
  );
}
