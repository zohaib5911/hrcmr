"use client";

import { Copy, RotateCw, TriangleAlert } from "lucide-react";
import { createElement, useState } from "react";

import { cn } from "@/lib/utils";

import { Button } from "./button";
import { Icon } from "./icon";

interface ErrorStateProps {
  title?: string;
  /** What happened and how to fix it. Never a stack trace (plan 5.8). */
  message: string;
  /** The API's request id, so support can find the failure. */
  requestId?: string;
  onRetry?: () => void;
  headingLevel?: 1 | 2 | 3 | 4;
  className?: string;
}

export function ErrorState({
  title = "Something went wrong",
  message,
  requestId,
  onRetry,
  headingLevel = 2,
  className,
}: ErrorStateProps) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (!requestId) return;
    try {
      await navigator.clipboard.writeText(requestId);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div
      role="alert"
      className={cn("flex flex-col items-center gap-3 px-6 py-12 text-center", className)}
    >
      <div className="bg-danger-tint text-danger rounded-pill grid size-16 place-items-center">
        <Icon icon={TriangleAlert} size={24} />
      </div>
      {createElement(`h${headingLevel}`, { className: "text-title-3 text-label" }, title)}
      <p className="text-body text-label-secondary max-w-sm">{message}</p>
      {requestId ? (
        <p className="text-footnote text-label-secondary flex flex-wrap items-center justify-center gap-2">
          <span>
            Request ID <code className="text-label font-mono">{requestId}</code>
          </span>
          <Button variant="plain" size="sm" onClick={copy} className="-my-1">
            <Icon icon={Copy} size={16} />
            {copied ? "Copied" : "Copy"}
          </Button>
        </p>
      ) : null}
      {onRetry ? (
        <Button variant="tinted" onClick={onRetry} className="mt-2">
          <Icon icon={RotateCw} size={16} />
          Try again
        </Button>
      ) : null}
    </div>
  );
}
