import fs from "node:fs";
import path from "node:path";

import { cn } from "@/lib/utils";

/** The folder the screenshots script writes to (web/tests/e2e/marketing-screenshots.spec.ts). */
const SHOT_DIR = path.join(process.cwd(), "public", "marketing");

/**
 * A real screenshot of the app in a plain browser frame (plan 5.9). The light and dark images are
 * swapped by the page theme. If the images have not been generated yet, nothing is shown.
 */
export function ProductShot({
  name,
  alt,
  className,
}: {
  name: string;
  alt: string;
  className?: string;
}) {
  const has = (theme: string) => fs.existsSync(path.join(SHOT_DIR, `${name}-${theme}.png`));
  if (!has("light") || !has("dark")) return null;
  return (
    <figure
      className={cn(
        "border-separator bg-elevated shadow-e3 overflow-hidden rounded-xl border",
        className,
      )}
    >
      <div
        aria-hidden
        className="border-separator bg-fill-secondary flex gap-1.5 border-b px-4 py-3"
      >
        <span className="bg-separator size-2.5 rounded-full" />
        <span className="bg-separator size-2.5 rounded-full" />
        <span className="bg-separator size-2.5 rounded-full" />
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element -- fixed files in /public, sized by the frame */}
      <img
        src={`/marketing/${name}-light.png`}
        alt={alt}
        loading="lazy"
        className="block w-full dark:hidden"
      />
      {/* eslint-disable-next-line @next/next/no-img-element -- as above */}
      <img
        src={`/marketing/${name}-dark.png`}
        alt={alt}
        loading="lazy"
        className="hidden w-full dark:block"
      />
    </figure>
  );
}
