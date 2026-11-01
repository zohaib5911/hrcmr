"use client";

import { Monitor, Moon, Sun, UserRound } from "lucide-react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { IconButton } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Menu,
  MenuContent,
  MenuItem,
  MenuLabel,
  MenuRadioGroup,
  MenuRadioItem,
  MenuSeparator,
  MenuTrigger,
} from "@/components/ui/menu";
import { parseTheme, type ThemeChoice } from "@/lib/theme";
import { applyTheme } from "@/lib/theme-dom";

import type { ShellUser } from "./shell-types";

/** The person's menu, top right: their profile, and the colour theme (plan 5.3: chosen in My Profile). */
export function AvatarMenu({ user, theme }: { user: ShellUser | null; theme: ThemeChoice }) {
  const [choice, setChoice] = useState(theme);
  const router = useRouter();
  return (
    <Menu>
      <MenuTrigger asChild>
        <IconButton label="Account menu" className="size-auto! p-1">
          {user ? <Avatar name={user.name} size="sm" decorative /> : <Icon icon={UserRound} />}
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        {user ? (
          <>
            <div className="px-3 py-2">
              <p className="text-callout text-label font-medium">{user.name}</p>
              <p className="text-footnote text-label-secondary">{user.email}</p>
            </div>
            <MenuSeparator />
          </>
        ) : null}
        <MenuItem
          icon={<Icon icon={UserRound} size={16} />}
          onSelect={() => router.push("/profile" as Route)}
        >
          My profile
        </MenuItem>
        <MenuSeparator />
        <MenuLabel>Appearance</MenuLabel>
        <MenuRadioGroup
          value={choice}
          onValueChange={(next) => {
            const parsed = parseTheme(next);
            setChoice(parsed);
            applyTheme(parsed, document, window.location.protocol === "https:");
          }}
        >
          <MenuRadioItem value="system">
            <span className="flex items-center gap-2">
              <Icon icon={Monitor} size={16} /> System
            </span>
          </MenuRadioItem>
          <MenuRadioItem value="light">
            <span className="flex items-center gap-2">
              <Icon icon={Sun} size={16} /> Light
            </span>
          </MenuRadioItem>
          <MenuRadioItem value="dark">
            <span className="flex items-center gap-2">
              <Icon icon={Moon} size={16} /> Dark
            </span>
          </MenuRadioItem>
        </MenuRadioGroup>
      </MenuContent>
    </Menu>
  );
}
