import type { FaqItem } from "@/components/marketing/faq";
import { resourceTools } from "@/lib/resources";

/**
 * Content types for the shared public calculator frame (plan L1479): quick answer, preset
 * scenario chips, numbered steps, how it works and FAQ. Each calculator group fills these in.
 */

export type ResourceToolSlug = (typeof resourceTools)[number]["slug"];

/**
 * Where a tool's answers go. `memory`: page memory only. `local_draft`: saved in this browser's
 * local storage (risk assessment draft). `soc_lookup`: only the occupation search is sent to the
 * approved public SOC lookup (decision C4.1.9).
 */
export type CalculatorPrivacyMode = "memory" | "local_draft" | "soc_lookup";

export const privacyNotices: Record<CalculatorPrivacyMode, string> = {
  memory: "Your answers stay in this page’s memory. Nothing you enter is saved or sent.",
  local_draft:
    "Your draft is saved only in this browser (local storage) and is never sent anywhere. Clear it at any time.",
  soc_lookup:
    "Only your SOC code or job title search is sent to the public occupation lookup. Salary and personal answers stay in this page’s memory and are not saved or sent.",
};

/** A preset scenario chip: fills the form with example values; the calculator owns the state. */
export interface CalculatorPreset<Values> {
  id: string;
  label: string;
  values: Values;
}

/** One numbered step, used by the step form and by "How it works". */
export interface CalculatorStep {
  title: string;
  body: string;
}

export interface CalculatorFrameContent {
  /** One or two sentences answering the page's main question before the form. */
  quickAnswer?: string;
  howItWorks?: readonly CalculatorStep[];
  faq?: readonly FaqItem[];
}

/** Other published tools for the "More tools" list, excluding the current one. */
export function relatedTools(current: ResourceToolSlug | undefined, count = 3) {
  return resourceTools.filter((tool) => tool.slug !== current).slice(0, count);
}
