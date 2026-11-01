"use client";

import { Check, ChevronDown, LoaderCircle } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { Icon } from "./icon";
import { Popover, PopoverAnchor, PopoverContent } from "./popover";
import { TextField, type TextFieldProps } from "./text-field";

export interface ComboboxOption {
  value: string;
  label: string;
  description?: string;
}

type ComboboxProps = Omit<
  TextFieldProps,
  "value" | "defaultValue" | "onChange" | "type" | "role" | "endAdornment" | "clearable"
> & {
  value: ComboboxOption | null;
  onChange: (option: ComboboxOption | null) => void;
  /** A fixed list, filtered as you type. */
  options?: readonly ComboboxOption[];
  /** Or a search, run as you type (after `debounceMs`). Use an `AbortSignal` to cancel stale searches. */
  loadOptions?: (query: string, signal: AbortSignal) => Promise<readonly ComboboxOption[]>;
  debounceMs?: number;
  /** Characters needed before `loadOptions` runs. */
  minChars?: number;
  emptyText?: string;
};

function filterStatic(
  options: readonly ComboboxOption[],
  query: string,
): readonly ComboboxOption[] {
  const needle = query.trim().toLocaleLowerCase("en-GB");
  if (!needle) return options;
  return options.filter((o) =>
    `${o.label} ${o.description ?? ""}`.toLocaleLowerCase("en-GB").includes(needle),
  );
}

/**
 * Pick one item from a long list by typing (ARIA 1.2 combobox). Focus stays in the text box; the arrow
 * keys move a highlight through the list, Enter chooses, Esc closes. Results can come from a search.
 */
export function Combobox({
  value,
  onChange,
  options,
  loadOptions,
  debounceMs = 250,
  minChars = 1,
  emptyText = "No matches",
  onKeyDown,
  onBlur,
  ...props
}: ComboboxProps) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  // What is typed. `null` means "show the chosen item's label".
  const [draft, setDraft] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const [remote, setRemote] = useState<{ query: string; items: readonly ComboboxOption[] } | null>(
    null,
  );
  const [failed, setFailed] = useState(false);
  const anchor = useRef<HTMLDivElement>(null);

  const query = draft ?? "";
  const searching = loadOptions !== undefined && query.trim().length >= minChars;
  const loading = searching && (remote === null || remote.query !== query);
  const items: readonly ComboboxOption[] = searching
    ? remote?.query === query
      ? remote.items
      : []
    : loadOptions
      ? []
      : filterStatic(options ?? [], query);
  const activeIndex = Math.min(active, Math.max(items.length - 1, 0));

  useEffect(() => {
    if (!searching || !loadOptions) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      loadOptions(query, controller.signal)
        .then((result) => {
          if (controller.signal.aborted) return;
          setFailed(false);
          setRemote({ query, items: result });
        })
        .catch(() => {
          if (controller.signal.aborted) return;
          setFailed(true);
          setRemote({ query, items: [] });
        });
    }, debounceMs);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [searching, query, loadOptions, debounceMs]);

  function choose(option: ComboboxOption) {
    onChange(option);
    setDraft(null);
    setOpen(false);
  }

  const optionId = (index: number) => `${listId}-option-${index}`;
  const status = loading
    ? "Searching…"
    : failed
      ? "Search failed. Try again."
      : items.length === 0
        ? emptyText
        : `${items.length} ${items.length === 1 ? "result" : "results"} available`;

  return (
    <Popover open={open && (items.length > 0 || draft !== null)} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <div ref={anchor}>
          <TextField
            {...props}
            type="text"
            role="combobox"
            autoComplete="off"
            clearable={false}
            aria-expanded={open}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={open && items.length > 0 ? optionId(activeIndex) : undefined}
            value={draft ?? value?.label ?? ""}
            endAdornment={
              <Icon
                icon={loading ? LoaderCircle : ChevronDown}
                size={16}
                className={loading ? "animate-spin motion-reduce:animate-pulse" : undefined}
              />
            }
            onChange={(event) => {
              setDraft(event.target.value);
              setActive(0);
              setOpen(true);
              if (value) onChange(null);
            }}
            onFocus={() => setOpen(true)}
            onBlur={(event) => {
              setOpen(false);
              setDraft(null);
              onBlur?.(event);
            }}
            onKeyDown={(event) => {
              onKeyDown?.(event);
              if (event.defaultPrevented) return;
              if (event.key === "ArrowDown") {
                event.preventDefault();
                if (!open) setOpen(true);
                else setActive(Math.min(activeIndex + 1, items.length - 1));
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setActive(Math.max(activeIndex - 1, 0));
              } else if (event.key === "Enter" && open && items[activeIndex]) {
                event.preventDefault();
                choose(items[activeIndex]);
              } else if (event.key === "Escape" && open) {
                event.preventDefault();
                setOpen(false);
              }
            }}
          />
        </div>
      </PopoverAnchor>
      <PopoverContent
        role="presentation"
        className="w-[var(--radix-popover-trigger-width)] overflow-hidden p-1"
        onOpenAutoFocus={(event) => event.preventDefault()}
        onCloseAutoFocus={(event) => event.preventDefault()}
        onInteractOutside={(event) => {
          if (anchor.current?.contains(event.target as Node)) event.preventDefault();
        }}
      >
        <ul
          id={listId}
          role="listbox"
          aria-label={props.label}
          className="max-h-72 overflow-y-auto"
        >
          {items.map((option, index) => (
            <li
              key={option.value}
              id={optionId(index)}
              role="option"
              aria-selected={value?.value === option.value}
              data-active={index === activeIndex || undefined}
              // Keeps focus in the text box while clicking.
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(option)}
              onMouseMove={() => setActive(index)}
              className={cn(
                "rounded-control text-body flex cursor-pointer items-center justify-between gap-3 px-3 py-2",
                "data-[active]:bg-accent-tint",
              )}
            >
              <span className="min-w-0">
                <span className="text-label block truncate">{option.label}</span>
                {option.description ? (
                  <span className="text-footnote text-label-secondary block truncate [[data-active]_&]:text-label">
                    {option.description}
                  </span>
                ) : null}
              </span>
              {value?.value === option.value ? (
                <Icon icon={Check} size={16} className="text-accent-text shrink-0" />
              ) : null}
            </li>
          ))}
        </ul>
        {items.length === 0 ? (
          <p className="text-callout text-label-secondary px-3 py-2">{status}</p>
        ) : null}
        <p role="status" className="sr-only">
          {status}
        </p>
      </PopoverContent>
    </Popover>
  );
}
