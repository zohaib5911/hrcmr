import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

/**
 * The building blocks of the public website's pages (plan 5.9): full-width sections that alternate
 * between the page colour and the raised colour, centred copy at 720 px, and feature grids of three
 * or four tiles. Pages are made by stacking these.
 */

export interface Action {
  label: string;
  href: Route;
  variant?: "filled" | "tinted" | "gray" | "plain";
}

function Actions({ actions, className }: { actions: readonly Action[]; className?: string }) {
  if (actions.length === 0) return null;
  return (
    <div className={cn("flex flex-wrap items-center gap-3", className)}>
      {actions.map((action) => (
        <Button key={action.href} asChild size="lg" variant={action.variant ?? "filled"}>
          <Link href={action.href} prefetch={false}>
            {action.label}
          </Link>
        </Button>
      ))}
    </div>
  );
}

interface SectionProps {
  /** "raised" is the white (dark: grey) band, "page" is the page colour. Alternate them down a page. */
  tone?: "raised" | "page";
  id?: string;
  /** The accessible name of the section, when it has no visible heading of its own. */
  label?: string;
  className?: string;
  children: ReactNode;
}

export function Section({ tone = "raised", id, label, className, children }: SectionProps) {
  return (
    <section
      id={id}
      aria-label={label}
      className={cn(tone === "raised" ? "bg-elevated" : "bg-canvas", "py-16 md:py-24", className)}
    >
      <div className="page-marketing">{children}</div>
    </section>
  );
}

interface HeadingProps {
  title: string;
  lead?: string;
  eyebrow?: string;
  /** Use 1 only once per page, for the hero. */
  level?: 1 | 2;
  /** On a tinted background the lead needs the stronger text colour to stay readable. */
  strongLead?: boolean;
  className?: string;
}

/** A centred title with an optional eyebrow above and a lead paragraph below, 720 px at most. */
export function SectionHeading({
  title,
  lead,
  eyebrow,
  level = 2,
  strongLead = false,
  className,
}: HeadingProps) {
  const Heading = level === 1 ? "h1" : "h2";
  return (
    <div className={cn("mx-auto max-w-[45rem] text-center", className)}>
      {eyebrow ? (
        <p className="text-headline text-accent-text mb-3 tracking-wide uppercase">{eyebrow}</p>
      ) : null}
      <Heading
        className={cn(
          level === 1 ? "text-hero" : "text-section font-bold tracking-tight",
          "text-label text-balance",
        )}
      >
        {title}
      </Heading>
      {lead ? (
        <p
          className={cn(
            "text-lead mt-5 text-pretty",
            strongLead ? "text-label" : "text-label-secondary",
          )}
        >
          {lead}
        </p>
      ) : null}
    </div>
  );
}

interface HeroProps {
  title: string;
  lead: string;
  eyebrow?: string;
  actions?: readonly Action[];
  /** A product shot or illustration under the buttons. */
  children?: ReactNode;
}

/** A huge headline, a short sub-head and one pair of buttons: the first thing on a page. */
export function Hero({ title, lead, eyebrow, actions = [], children }: HeroProps) {
  return (
    <Section tone="page" className="pt-16 pb-12 md:pt-28 md:pb-20">
      <SectionHeading level={1} title={title} lead={lead} eyebrow={eyebrow} />
      <Actions actions={actions} className="mt-8 justify-center" />
      {children ? <div className="mt-12 md:mt-16">{children}</div> : null}
    </Section>
  );
}

export interface Feature {
  icon: LucideIcon;
  title: string;
  body: string;
}

/** Three or four tiles, each with an icon, a short title and a sentence or two. */
export function FeatureGrid({
  features,
  columns = 3,
  className,
}: {
  features: readonly Feature[];
  columns?: 3 | 4;
  className?: string;
}) {
  return (
    <ul
      className={cn(
        "grid gap-4 sm:grid-cols-2",
        columns === 3 ? "lg:grid-cols-3" : "lg:grid-cols-4",
        className,
      )}
    >
      {features.map((feature) => (
        <li key={feature.title} className="rounded-card border-separator border p-6">
          <span className="bg-accent-tint text-accent-text mb-4 inline-flex size-11 items-center justify-center rounded-full">
            <Icon icon={feature.icon} size={24} />
          </span>
          <h3 className="text-title-3 text-label">{feature.title}</h3>
          <p className="text-body text-label-secondary mt-2">{feature.body}</p>
        </li>
      ))}
    </ul>
  );
}

interface BandProps {
  tone?: "raised" | "page";
  title: string;
  lead: string;
  eyebrow?: string;
  points?: readonly string[];
  /** A screenshot or illustration. It sits beside the words from 768 px and below them on a phone. */
  media?: ReactNode;
  /** Put the media on the left. Alternate this down a page. */
  mediaFirst?: boolean;
  actions?: readonly Action[];
}

/** Words on one side, a picture on the other. Full width, with the colour alternating down the page. */
export function Band({
  tone = "raised",
  title,
  lead,
  eyebrow,
  points = [],
  media,
  mediaFirst = false,
  actions = [],
}: BandProps) {
  return (
    <Section tone={tone}>
      <div className="grid items-center gap-10 md:grid-cols-2 md:gap-16">
        <div className={cn(mediaFirst && "md:order-2")}>
          {eyebrow ? (
            <p className="text-headline text-accent-text mb-3 tracking-wide uppercase">{eyebrow}</p>
          ) : null}
          <h2 className="text-section text-label font-bold tracking-tight text-balance">{title}</h2>
          <p className="text-lead text-label-secondary mt-5 text-pretty">{lead}</p>
          {points.length > 0 ? (
            <ul className="mt-6 flex flex-col gap-3">
              {points.map((point) => (
                <li key={point} className="text-body text-label flex gap-3">
                  <span aria-hidden className="bg-accent mt-2 size-1.5 shrink-0 rounded-full" />
                  {point}
                </li>
              ))}
            </ul>
          ) : null}
          <Actions actions={actions} className="mt-8" />
        </div>
        {media ? <div className={cn(mediaFirst && "md:order-1")}>{media}</div> : null}
      </div>
    </Section>
  );
}

/** The closing call to action: one sentence and one or two buttons. */
export function CtaBand({
  title,
  lead,
  actions,
}: {
  title: string;
  lead?: string;
  actions: readonly Action[];
}) {
  return (
    <section aria-label="Get started" className="bg-accent-tint py-16 md:py-24">
      <div className="page-marketing">
        <SectionHeading title={title} lead={lead} strongLead />
        <Actions actions={actions} className="mt-8 justify-center" />
      </div>
    </section>
  );
}
