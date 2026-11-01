import type { Metadata } from "next";
import { cookies } from "next/headers";

import { ThemeSwitch } from "@/components/app/theme-switch";
import { MARKETING_STYLES, SPACING_STEPS, TYPE_STYLES } from "@/lib/design/catalog";
import { DURATION, SPRING } from "@/lib/motion";
import { THEME_COOKIE, parseTheme } from "@/lib/theme";

import { ThemePanel } from "./_components/theme-panel";

export const metadata: Metadata = {
  title: "Design tokens",
  robots: { index: false, follow: false },
};

const MARKETING_SAMPLES: Record<string, string> = {
  hero: "Compliance without the chase",
  section: "Everything your sponsor licence needs",
  lead: "Keep every check, report and deadline in one calm place, with plain-language reminders.",
};

/**
 * The design system on one page (plan.md T1.1): every token in both themes, the type scale, radius,
 * elevation, spacing and motion.
 *
 * Development only, and not by a check at run time: the file is named `page.dev.tsx`, and
 * next.config.ts enables the `dev.tsx` page extension only outside production. In a production build
 * this route is never compiled, so it cannot be served, and its text is nowhere in the output.
 */
export default async function DesignPage() {
  const theme = parseTheme((await cookies()).get(THEME_COOKIE)?.value);

  return (
    <main className="page-app flex flex-col gap-12 py-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-large-title">Design tokens</h1>
          <p className="text-callout text-label-secondary">
            Development only. Everything here is built from the tokens in app/globals.css.
          </p>
        </div>
        <ThemeSwitch initial={theme} />
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <ThemePanel theme="light" />
        <ThemePanel theme="dark" />
      </div>

      <section aria-labelledby="type-title" className="flex flex-col gap-4">
        <h2 id="type-title" className="text-title-2">
          Typography
        </h2>
        <ul className="bg-elevated rounded-card shadow-e1 divide-separator divide-y">
          {TYPE_STYLES.map((style) => (
            <li
              key={style.key}
              data-type-style={style.key}
              className="grid items-baseline gap-x-6 gap-y-1 p-4 md:grid-cols-[12rem_1fr]"
            >
              <p className="text-footnote text-label-secondary">
                {style.label}
                <br />
                <span className="tabular-nums">
                  {style.size} / {style.lineHeight} · {style.weight} · {style.tracking}
                </span>
              </p>
              <p className={style.utility}>Sponsor licence compliance, made calm</p>
            </li>
          ))}
        </ul>
        <ul className="bg-elevated rounded-card shadow-e1 divide-separator divide-y">
          {MARKETING_STYLES.map((style) => (
            <li
              key={style.key}
              data-type-style={style.key}
              className="flex flex-col gap-2 overflow-hidden p-4"
            >
              <p className="text-footnote text-label-secondary">
                {style.label} · {style.desktopMin}–{style.desktopMax} px on desktop, {style.floor}{" "}
                px on phones
              </p>
              <p className={style.utility}>{MARKETING_SAMPLES[style.key]}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="space-title" className="flex flex-col gap-4">
        <h2 id="space-title" className="text-title-2">
          Spacing on a 4 px grid
        </h2>
        <ul className="bg-elevated rounded-card shadow-e1 flex flex-col gap-2 p-4">
          {SPACING_STEPS.map((spacing) => (
            <li key={spacing.step} className="flex items-center gap-4">
              <span className="text-footnote text-label-secondary w-24 tabular-nums">
                {spacing.step} · {spacing.px} px
              </span>
              <span className={`${spacing.bar} bg-accent h-3 rounded-sm`} />
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="motion-title" className="flex flex-col gap-4">
        <h2 id="motion-title" className="text-title-2">
          Motion
        </h2>
        <div className="bg-elevated rounded-card shadow-e1 flex flex-col gap-3 p-4">
          <p className="text-callout">
            Spring: stiffness {SPRING.stiffness}, damping {SPRING.damping}, mass {SPRING.mass}.
            Durations: micro {DURATION.micro * 1000} ms, small {DURATION.small * 1000} ms, sheet{" "}
            {DURATION.sheet * 1000} ms. With reduced motion, things fade and never move.
          </p>
          <ul className="flex flex-wrap gap-3">
            <li className="bg-fill-secondary rounded-control motion-micro text-footnote hover:bg-accent hover:text-on-accent px-4 py-3 transition-colors">
              Hover me · micro
            </li>
            <li className="bg-fill-secondary rounded-control motion-small text-footnote hover:bg-accent hover:text-on-accent px-4 py-3 transition-colors">
              Hover me · small
            </li>
            <li className="bg-fill-secondary rounded-control motion-sheet text-footnote hover:bg-accent hover:text-on-accent px-4 py-3 transition-colors">
              Hover me · sheet
            </li>
          </ul>
        </div>
      </section>
    </main>
  );
}
