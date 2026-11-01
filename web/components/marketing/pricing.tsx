"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { Slider } from "radix-ui";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

import type { Action } from "./sections";

export interface Plan {
  id: string;
  name: string;
  /** Shown big, such as "£50". The caller formats it from the Stripe price, never from a constant here. */
  price: string;
  /** What the price covers, such as "a year" or "once, for ten years". */
  cadence: string;
  description: string;
  features: readonly string[];
  action: Action;
  /** The recommended plan: raised, with a "Best value" pill. */
  highlighted?: boolean;
}

/** Two large plan cards side by side, the recommended one highlighted (plan 5.9). */
export function PricingCards({ plans }: { plans: readonly Plan[] }) {
  return (
    <ul className="mx-auto grid max-w-4xl gap-6 md:grid-cols-2">
      {plans.map((plan) => (
        <li
          key={plan.id}
          className={cn(
            "rounded-sheet bg-elevated relative flex flex-col p-6 md:p-8",
            plan.highlighted ? "border-accent border-2" : "border-separator border",
          )}
        >
          {plan.highlighted ? (
            <span className="bg-accent text-on-accent rounded-pill text-footnote absolute -top-3 left-6 px-3 py-1 font-semibold">
              Best value
            </span>
          ) : null}
          <h3 className="text-title-2 text-label">{plan.name}</h3>
          <p className="mt-4 flex flex-wrap items-baseline gap-x-2">
            <span className="text-section text-label font-bold tracking-tight">{plan.price}</span>
            <span className="text-body text-label-secondary">{plan.cadence}</span>
          </p>
          <p className="text-body text-label-secondary mt-3">{plan.description}</p>
          <ul className="mt-6 flex flex-1 flex-col gap-3">
            {plan.features.map((feature) => (
              <li key={feature} className="text-body text-label flex gap-3">
                <Icon icon={Check} className="text-success mt-0.5" />
                {feature}
              </li>
            ))}
          </ul>
          <Button
            asChild
            size="lg"
            variant={plan.highlighted ? "filled" : "tinted"}
            className="mt-8 w-full"
          >
            <Link href={plan.action.href}>{plan.action.label}</Link>
          </Button>
        </li>
      ))}
    </ul>
  );
}

export interface SliderPlan {
  id: string;
  name: string;
  /** What the company pays, in pounds, for `years` years. */
  amount: number;
  years: number;
}

const POUNDS = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });

/** What each person costs per year at a headcount: the plan's price over its years, shared out. */
export function perPersonPerYear(plan: SliderPlan, headcount: number): number {
  return plan.amount / plan.years / Math.max(headcount, 1);
}

/**
 * A live headcount slider (plan 5.9): drag it to see the price per person per year fall as the team
 * grows. Prices come in as props, so the real amounts stay in one place (Stripe's price ids).
 */
export function HeadcountSlider({
  plans,
  min = 1,
  max = 250,
  initial = 10,
}: {
  plans: readonly SliderPlan[];
  min?: number;
  max?: number;
  initial?: number;
}) {
  const [headcount, setHeadcount] = useState(initial);
  return (
    <div className="rounded-sheet border-separator bg-elevated mx-auto max-w-4xl border p-6 md:p-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span id="headcount-label" className="text-headline text-label">
          How many people work for you?
        </span>
        <output aria-live="polite" className="text-title-2 text-label">
          {headcount} {headcount === 1 ? "person" : "people"}
        </output>
      </div>
      <Slider.Root
        value={[headcount]}
        min={min}
        max={max}
        step={1}
        onValueChange={([value]) => setHeadcount(value ?? initial)}
        className="relative my-6 flex h-6 w-full touch-none items-center select-none"
      >
        <Slider.Track className="bg-fill-secondary rounded-pill relative h-1.5 grow">
          <Slider.Range className="bg-accent rounded-pill absolute h-full" />
        </Slider.Track>
        <Slider.Thumb
          aria-labelledby="headcount-label"
          className="shadow-e2 border-separator bg-knob block size-7 rounded-full border outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        />
      </Slider.Root>
      <dl className="grid gap-4 sm:grid-cols-2">
        {plans.map((plan) => (
          <div key={plan.id} className="bg-canvas rounded-card p-4">
            <dt className="text-callout text-label-secondary">{plan.name}</dt>
            <dd className="text-title-1 text-label mt-1">
              {POUNDS.format(perPersonPerYear(plan, headcount))}
              <span className="text-callout text-label-secondary ml-2 font-normal">
                per person, per year
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
