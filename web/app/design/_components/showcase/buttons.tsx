"use client";

import { ArrowRight, Plus, Settings, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button, IconButton } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Tooltip } from "@/components/ui/tooltip";

import { Demo, DocSection, State } from "./doc";

const VARIANTS = ["filled", "tinted", "gray", "plain", "destructive"] as const;
const SIZES = ["sm", "md", "lg"] as const;

function LoadingButton() {
  const [loading, setLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  return (
    <Button
      loading={loading}
      onClick={() => {
        setLoading(true);
        timer.current = setTimeout(() => setLoading(false), 1800);
      }}
    >
      Save changes
    </Button>
  );
}

export function ButtonsSection() {
  return (
    <DocSection
      id="buttons"
      title="Buttons"
      description="One filled button per view. Every button is at least 32 px high with a mouse and 44 px on touch, and gives focus back where it found it."
    >
      <Demo
        title="Variants and sizes"
        note="Filled is the main action. Destructive is only for what cannot be undone."
      >
        <div className="flex w-full flex-col gap-3">
          {VARIANTS.map((variant) => (
            <div key={variant} className="flex flex-wrap items-center gap-3">
              <span className="text-footnote text-label-secondary w-24">{variant}</span>
              {SIZES.map((size) => (
                <Button key={size} variant={variant} size={size}>
                  {size === "sm" ? "Small" : size === "md" ? "Medium" : "Large"}
                </Button>
              ))}
              <Button variant={variant}>
                <Icon icon={Plus} size={16} />
                With icon
              </Button>
              <Button variant={variant} disabled>
                Disabled
              </Button>
            </div>
          ))}
        </div>
      </Demo>
      <Demo
        title="Loading keeps the width"
        note="The spinner replaces nothing: the label stays in place, unseen, so the button never jumps."
      >
        <State label="Click to load">
          <LoadingButton />
        </State>
        <State label="Always loading">
          <Button loading variant="tinted">
            Submitting
          </Button>
        </State>
      </Demo>
      <Demo
        title="Icon buttons and links"
        note="An icon-only button needs a label for screen readers; a tooltip tells everyone else."
      >
        <Tooltip content="Add employee">
          <IconButton label="Add employee" variant="filled">
            <Icon icon={Plus} />
          </IconButton>
        </Tooltip>
        <Tooltip content="Settings">
          <IconButton label="Settings" variant="gray">
            <Icon icon={Settings} />
          </IconButton>
        </Tooltip>
        <Tooltip content="Delete">
          <IconButton label="Delete" variant="plain">
            <Icon icon={Trash2} />
          </IconButton>
        </Tooltip>
        <Button asChild variant="tinted">
          <a href="#buttons">
            A link styled as a button
            <Icon icon={ArrowRight} size={16} />
          </a>
        </Button>
      </Demo>
    </DocSection>
  );
}
