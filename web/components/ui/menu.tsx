"use client";

import { Check } from "lucide-react";
import { ContextMenu as ContextPrimitive, DropdownMenu as MenuPrimitive } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Icon } from "./icon";

export const Menu = MenuPrimitive.Root;
export const MenuTrigger = MenuPrimitive.Trigger;
export const MenuGroup = MenuPrimitive.Group;
export const MenuRadioGroup = MenuPrimitive.RadioGroup;

export const ContextMenu = ContextPrimitive.Root;
export const ContextMenuTrigger = ContextPrimitive.Trigger;

const panel = cn(
  "material-sheet rounded-popover shadow-e2 text-body text-label z-50 min-w-48 overflow-hidden p-1 outline-none",
  "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
  "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
  "duration-[var(--duration-small)] motion-reduce:data-[state=open]:zoom-in-100 motion-reduce:data-[state=closed]:zoom-out-100",
);

const item = cn(
  "rounded-control relative flex cursor-pointer items-center gap-2.5 px-3 py-2 outline-none select-none",
  "data-[highlighted]:bg-accent-tint data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
);

const DESTRUCTIVE = "text-danger";

export function MenuContent({
  className,
  sideOffset = 6,
  align = "end",
  ...props
}: ComponentProps<typeof MenuPrimitive.Content>) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Content
        sideOffset={sideOffset}
        align={align}
        collisionPadding={12}
        className={cn(panel, className)}
        {...props}
      />
    </MenuPrimitive.Portal>
  );
}

interface ItemExtras {
  icon?: ReactNode;
  /** A keyboard shortcut shown on the right, such as "⌘E". */
  shortcut?: string;
  destructive?: boolean;
}

export function MenuItem({
  icon,
  shortcut,
  destructive,
  className,
  children,
  ...props
}: ComponentProps<typeof MenuPrimitive.Item> & ItemExtras) {
  return (
    <MenuPrimitive.Item className={cn(item, destructive && DESTRUCTIVE, className)} {...props}>
      {icon ? <span className="shrink-0">{icon}</span> : null}
      <span className="flex-1">{children}</span>
      {shortcut ? (
        <kbd className="text-footnote text-label-secondary font-sans">{shortcut}</kbd>
      ) : null}
    </MenuPrimitive.Item>
  );
}

export function MenuCheckboxItem({
  className,
  children,
  ...props
}: ComponentProps<typeof MenuPrimitive.CheckboxItem>) {
  return (
    <MenuPrimitive.CheckboxItem className={cn(item, "pl-9", className)} {...props}>
      <MenuPrimitive.ItemIndicator className="absolute left-3">
        <Icon icon={Check} size={16} />
      </MenuPrimitive.ItemIndicator>
      {children}
    </MenuPrimitive.CheckboxItem>
  );
}

export function MenuRadioItem({
  className,
  children,
  ...props
}: ComponentProps<typeof MenuPrimitive.RadioItem>) {
  return (
    <MenuPrimitive.RadioItem className={cn(item, "pl-9", className)} {...props}>
      <MenuPrimitive.ItemIndicator className="absolute left-3">
        <Icon icon={Check} size={16} />
      </MenuPrimitive.ItemIndicator>
      {children}
    </MenuPrimitive.RadioItem>
  );
}

export function MenuLabel({ className, ...props }: ComponentProps<typeof MenuPrimitive.Label>) {
  return (
    <MenuPrimitive.Label
      className={cn("text-caption text-label-secondary px-3 py-1.5 font-medium", className)}
      {...props}
    />
  );
}

export function MenuSeparator({
  className,
  ...props
}: ComponentProps<typeof MenuPrimitive.Separator>) {
  return (
    <MenuPrimitive.Separator className={cn("bg-separator -mx-1 my-1 h-px", className)} {...props} />
  );
}

export function ContextMenuContent({
  className,
  ...props
}: ComponentProps<typeof ContextPrimitive.Content>) {
  return (
    <ContextPrimitive.Portal>
      <ContextPrimitive.Content collisionPadding={12} className={cn(panel, className)} {...props} />
    </ContextPrimitive.Portal>
  );
}

export function ContextMenuItem({
  icon,
  shortcut,
  destructive,
  className,
  children,
  ...props
}: ComponentProps<typeof ContextPrimitive.Item> & ItemExtras) {
  return (
    <ContextPrimitive.Item className={cn(item, destructive && DESTRUCTIVE, className)} {...props}>
      {icon ? <span className="shrink-0">{icon}</span> : null}
      <span className="flex-1">{children}</span>
      {shortcut ? (
        <kbd className="text-footnote text-label-secondary font-sans">{shortcut}</kbd>
      ) : null}
    </ContextPrimitive.Item>
  );
}

export function ContextMenuSeparator({
  className,
  ...props
}: ComponentProps<typeof ContextPrimitive.Separator>) {
  return (
    <ContextPrimitive.Separator
      className={cn("bg-separator -mx-1 my-1 h-px", className)}
      {...props}
    />
  );
}
