"use client";

import { Search, X } from "lucide-react";
import { useRef, type ComponentProps } from "react";

import { cn } from "@/lib/utils";

import { IconButton } from "./button";
import { mergeRefs, setNativeValue } from "./field";
import { Icon } from "./icon";

type SearchFieldProps = Omit<ComponentProps<"input">, "type" | "size"> & {
  /** What is being searched. It is the field's accessible name and its placeholder. */
  label: string;
  /** A shortcut to show while the field is empty, such as "⌘K". */
  shortcut?: string;
  containerClassName?: string;
  /**
   * Marks this as the search box for the list on the page, so pressing "/" anywhere moves the cursor
   * here (plan 8.19). Give it to one field per page.
   */
  listSearch?: boolean;
};

/** A rounded search box (plan 5.7). Search as you type: the caller listens to `onChange`. */
export function SearchField({
  label,
  shortcut,
  containerClassName,
  listSearch,
  className,
  ref,
  ...props
}: SearchFieldProps) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div
      className={cn(
        "group/search bg-fill-secondary rounded-pill relative flex h-10 items-center gap-2 pr-2 pl-3",
        "focus-within:outline-accent focus-within:outline-2 focus-within:outline-offset-2",
        containerClassName,
      )}
    >
      <Icon icon={Search} size={16} className="text-label-secondary" />
      <input
        {...props}
        ref={mergeRefs(input, ref)}
        type="search"
        role="searchbox"
        data-list-search={listSearch ? "" : undefined}
        aria-label={label}
        placeholder={label}
        className={cn(
          "peer text-body text-label placeholder:text-placeholder h-full min-w-0 flex-1 bg-transparent outline-none",
          "[&::-webkit-search-cancel-button]:hidden",
          className,
        )}
      />
      {shortcut ? (
        <kbd className="text-footnote text-label-secondary rounded-control bg-elevated shrink-0 px-1.5 py-0.5 font-sans group-focus-within/search:hidden group-has-[input:not(:placeholder-shown)]/search:hidden">
          {shortcut}
        </kbd>
      ) : null}
      <IconButton
        label={`Clear ${label.toLowerCase()}`}
        size="sm"
        variant="gray"
        tabIndex={-1}
        onClick={() => {
          if (input.current) {
            setNativeValue(input.current, "");
            input.current.focus();
          }
        }}
        className="rounded-pill group-has-[input:placeholder-shown]/search:hidden"
      >
        <Icon icon={X} size={16} />
      </IconButton>
    </div>
  );
}
