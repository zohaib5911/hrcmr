"use client";

import { CornerDownLeft, Search } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";

import { rankPages } from "@/lib/search";
import { cn } from "@/lib/utils";

import { OVERLAY_CLASSES } from "./dialog";
import { Icon } from "./icon";

export interface CommandItem {
  id: string;
  label: string;
  /** The group it belongs to ("People"). Searched as well as the label. */
  group: string;
  icon?: LucideIcon;
  /** Where it goes. The caller decides what choosing it does. */
  href: string;
}

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Everything that can be searched. */
  items: readonly CommandItem[];
  /** Shown first when nothing has been typed: pages visited lately. */
  recent?: readonly CommandItem[];
  /** People and candidates found by a live search (two characters or more). */
  remote?: readonly CommandItem[];
  /** Told each time the text changes, so the caller can search. */
  onQueryChange?: (query: string) => void;
  onSelect: (item: CommandItem) => void;
}

interface Row {
  item: CommandItem;
  section: string;
}

/**
 * Spotlight-style search (plan 5.7): press Cmd or Ctrl K, type a few letters, press Enter. The text
 * box keeps focus while the arrow keys move a highlight through the list (the ARIA combobox pattern),
 * Esc closes it and focus goes back to where it was.
 */
export function CommandPalette({
  open,
  onOpenChange,
  items,
  recent = [],
  remote = [],
  onQueryChange,
  onSelect,
}: CommandPaletteProps) {
  const listId = useId();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const list = useRef<HTMLUListElement>(null);

  const rows: Row[] = useMemo(() => {
    const sectionOf = (item: CommandItem) => (item.group === "Actions" ? "Actions" : "Pages");
    if (query.trim() === "") {
      return [
        ...recent.map((item) => ({ item, section: "Recent" })),
        ...items.map((item) => ({ item, section: sectionOf(item) })),
      ];
    }
    const people =
      query.trim().length >= 2 ? remote.map((item) => ({ item, section: "People" })) : [];
    return [
      ...people,
      ...rankPages(query, items).map((item) => ({ item, section: sectionOf(item) })),
    ];
  }, [query, items, recent, remote]);

  const current = Math.min(active, Math.max(rows.length - 1, 0));
  const optionId = (index: number) => `${listId}-option-${index}`;

  // Keep the highlighted row in view as the arrow keys move it.
  useEffect(() => {
    list.current
      ?.querySelector(`[id="${listId}-option-${current}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [current, listId]);

  function choose(row: Row | undefined) {
    if (!row) return;
    onSelect(row.item);
    onOpenChange(false);
  }

  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) {
          setQuery("");
          setActive(0);
        }
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className={OVERLAY_CLASSES} />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className={cn(
            "material-modal rounded-sheet shadow-e3 text-label fixed top-[8vh] left-1/2 z-50 flex max-h-[70vh] w-[min(40rem,calc(100vw-1.5rem))] -translate-x-1/2 flex-col overflow-hidden outline-none md:top-[14vh]",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-96",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-96",
            "duration-[var(--duration-small)] ease-(--ease-spring) motion-reduce:data-[state=open]:zoom-in-100 motion-reduce:data-[state=closed]:zoom-out-100",
          )}
        >
          <DialogPrimitive.Title className="sr-only">Search</DialogPrimitive.Title>
          <div className="border-separator flex items-center gap-3 border-b px-4">
            <Icon icon={Search} className="text-label-secondary" />
            <input
              role="combobox"
              aria-expanded="true"
              aria-controls={listId}
              aria-autocomplete="list"
              aria-activedescendant={rows.length > 0 ? optionId(current) : undefined}
              aria-label="Search pages"
              placeholder="Search pages"
              autoComplete="off"
              spellCheck={false}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActive(0);
                onQueryChange?.(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActive(rows.length === 0 ? 0 : (current + 1) % rows.length);
                } else if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActive(rows.length === 0 ? 0 : (current - 1 + rows.length) % rows.length);
                } else if (event.key === "Enter") {
                  event.preventDefault();
                  choose(rows[current]);
                }
              }}
              className="text-title-3 text-label placeholder:text-placeholder h-14 min-w-0 flex-1 bg-transparent outline-none"
            />
          </div>

          <ul
            id={listId}
            ref={list}
            role="listbox"
            aria-label="Results"
            className="min-h-0 flex-1 overflow-y-auto p-2"
          >
            {rows.map((row, index) => {
              const first = index === 0 || rows[index - 1]?.section !== row.section;
              return (
                <li key={`${row.section}-${row.item.id}`} role="presentation">
                  {first ? (
                    <p
                      role="presentation"
                      className="text-caption text-label-secondary px-3 pt-2 pb-1 font-medium tracking-wider uppercase"
                    >
                      {row.section}
                    </p>
                  ) : null}
                  <div
                    id={optionId(index)}
                    role="option"
                    aria-selected={index === current}
                    data-active={index === current || undefined}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => choose(row)}
                    onMouseMove={() => setActive(index)}
                    className="group rounded-control text-body data-[active]:bg-accent-tint flex cursor-pointer items-center gap-3 px-3 py-2.5"
                  >
                    {row.item.icon ? (
                      <Icon icon={row.item.icon} className="text-label-secondary shrink-0" />
                    ) : null}
                    <span className="min-w-0 flex-1 truncate">{row.item.label}</span>
                    <span className="text-footnote text-label-secondary group-data-[active]:text-label shrink-0">
                      {row.item.group}
                    </span>
                    {index === current ? (
                      <Icon
                        icon={CornerDownLeft}
                        size={16}
                        className="text-label-secondary shrink-0"
                      />
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>

          {rows.length === 0 ? (
            <p className="text-callout text-label-secondary px-5 py-8 text-center">
              No pages match &ldquo;{query.trim()}&rdquo;.
            </p>
          ) : null}
          <p role="status" className="sr-only">
            {rows.length === 0
              ? "No results"
              : `${rows.length} ${rows.length === 1 ? "result" : "results"}`}
          </p>

          <div className="border-separator text-footnote text-label-secondary flex items-center gap-4 border-t px-4 py-2.5 max-md:hidden">
            <span>↑ ↓ to move</span>
            <span>Enter to open</span>
            <span>Esc to close</span>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
