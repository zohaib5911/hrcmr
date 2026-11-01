"use client";

import { ChevronDown } from "lucide-react";
import { Accordion } from "radix-ui";

import { Icon } from "@/components/ui/icon";

export interface FaqItem {
  question: string;
  answer: string;
}

/**
 * Questions and answers (plan 5.9). Opens one at a time; the keyboard works as in any accordion
 * (Tab to a question, Enter or Space to open it, arrow keys to move between questions).
 */
export function Faq({ items }: { items: readonly FaqItem[] }) {
  return (
    <Accordion.Root
      type="single"
      collapsible
      className="rounded-card border-separator mx-auto max-w-[45rem] divide-y divide-[var(--separator)] border"
    >
      {items.map((item) => (
        <Accordion.Item key={item.question} value={item.question}>
          <Accordion.Header asChild>
            <h3>
              <Accordion.Trigger className="text-headline text-label group flex min-h-14 w-full items-center justify-between gap-4 px-5 py-3 text-left">
                {item.question}
                <Icon
                  icon={ChevronDown}
                  className="text-label-secondary transition-transform motion-small group-data-[state=open]:rotate-180 motion-reduce:transition-none"
                />
              </Accordion.Trigger>
            </h3>
          </Accordion.Header>
          <Accordion.Content className="text-body text-label-secondary overflow-hidden px-5 pb-5">
            {item.answer}
          </Accordion.Content>
        </Accordion.Item>
      ))}
    </Accordion.Root>
  );
}
