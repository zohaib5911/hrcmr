"use client";
import { Ellipsis } from "lucide-react";
import { IconButton } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Menu, MenuContent, MenuTrigger } from "@/components/ui/menu";
export function ActionMenu({
  label,
  children,
  disabled,
}: {
  label: string;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <Menu>
      <MenuTrigger asChild>
        <IconButton label={label} size="sm" disabled={disabled}>
          <Icon icon={Ellipsis} />
        </IconButton>
      </MenuTrigger>
      <MenuContent>{children}</MenuContent>
    </Menu>
  );
}
