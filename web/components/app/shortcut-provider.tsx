"use client";

import type { Route } from "next";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { CommandPalette, type CommandItem } from "@/components/ui/command-palette";
import { KeyboardShortcutsSheet } from "@/components/ui/shortcuts-sheet";
import { NAV_GROUPS, NAV_ITEMS, findNavItem } from "@/lib/navigation";
import { RECENT_PAGES_KEY, parseRecent, pushRecent, serialiseRecent } from "@/lib/recent-pages";
import { OPEN_PALETTE, OPEN_SHORTCUTS } from "@/lib/shell-events";
import { interpretKey, type SequenceState } from "@/lib/shortcuts";

import { useApple } from "./use-apple";

/** Every page the palette can open, with its group's name. */
const PAGE_ITEMS: readonly CommandItem[] = NAV_GROUPS.flatMap((group) =>
  group.items.map((item) => ({
    id: item.id,
    label: item.label,
    group: group.label,
    icon: item.icon,
    href: item.href,
  })),
);
const KNOWN_PAGES = NAV_ITEMS.map((item) => item.href);

interface ShortcutRegistry {
  /** Sets what "N" does on this page. Returns a function that takes it away again. */
  registerNew: (handler: () => void) => () => void;
}

const RegistryContext = createContext<ShortcutRegistry | null>(null);

/**
 * Tells the shell what the "N" key means on this page: add an employee, request leave, and so on. A
 * page that has nothing to add does not call it, and "N" then does nothing. Wrap `handler` in
 * `useCallback`.
 */
export function useNewShortcut(handler: () => void): void {
  const registry = useContext(RegistryContext);
  useEffect(() => registry?.registerNew(handler), [registry, handler]);
}

function readRecent(): string[] {
  try {
    return parseRecent(window.localStorage.getItem(RECENT_PAGES_KEY), KNOWN_PAGES);
  } catch {
    // Storage can be switched off or full. The palette works the same without it.
    return [];
  }
}

function writeRecent(list: readonly string[]): void {
  try {
    window.localStorage.setItem(RECENT_PAGES_KEY, serialiseRecent(list));
  } catch {
    // As above: remembering recent pages is a convenience, never a requirement.
  }
}

/** Anything the person has open on top of the page: a dialog, a sheet, a menu or a popover. */
function layerIsOpen(): boolean {
  return (
    document.querySelector(
      '[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"], [role="menu"][data-state="open"]',
    ) !== null
  );
}

/** The search box for the list on this page, if there is one and it can be seen. */
function findListSearch(): HTMLInputElement | null {
  for (const input of document.querySelectorAll<HTMLInputElement>("input[data-list-search]")) {
    if (input.getClientRects().length > 0) return input;
  }
  return null;
}

interface ShortcutProviderProps {
  /** Collapses or expands the sidebar ("["). */
  onToggleSidebar: () => void;
  children: ReactNode;
}

/**
 * The app's keyboard shortcuts (plan 8.19) and the two things they open: the command palette and the
 * shortcuts sheet. What each key means is decided in lib/shortcuts.ts; this component listens, acts,
 * and keeps out of the way of anything the person has open or is typing into.
 */
export function ShortcutProvider({ onToggleSidebar, children }: ShortcutProviderProps) {
  const router = useRouter();
  const pathname = usePathname();
  const apple = useApple();

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);

  const sequence = useRef<SequenceState>({ goAt: null });
  const newHandler = useRef<(() => void) | null>(null);

  const registry = useMemo<ShortcutRegistry>(
    () => ({
      registerNew: (handler) => {
        newHandler.current = handler;
        return () => {
          if (newHandler.current === handler) newHandler.current = null;
        };
      },
    }),
    [],
  );

  const openPalette = useCallback(() => {
    setRecent(readRecent());
    setPaletteOpen(true);
  }, []);

  // Remember the page for the palette's "Recent" list.
  useEffect(() => {
    const page = findNavItem(pathname);
    if (page) writeRecent(pushRecent(readRecent(), page.href));
  }, [pathname]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const result = interpretKey(event, sequence.current, Date.now());
      sequence.current = result.state;
      const action = result.action;
      if (!action) return;

      // While the palette or sheet is up, only its own key closes it; every other key belongs to it.
      if (paletteOpen || sheetOpen) {
        if (paletteOpen && action.type === "palette") setPaletteOpen(false);
        else if (sheetOpen && action.type === "shortcuts") setSheetOpen(false);
        else return;
        event.preventDefault();
        return;
      }
      // A dialog, menu or popover someone else opened keeps all its keys.
      if (layerIsOpen()) return;

      switch (action.type) {
        case "palette":
          openPalette();
          break;
        case "shortcuts":
          setSheetOpen(true);
          break;
        case "toggle-sidebar":
          onToggleSidebar();
          break;
        case "go":
          router.push(action.href as Route);
          break;
        case "focus-search": {
          const search = findListSearch();
          // No list search on this page: leave "/" to the browser.
          if (!search) return;
          search.focus();
          search.select();
          break;
        }
        case "new":
          // Nothing to add on this page: do nothing.
          if (!newHandler.current) return;
          newHandler.current();
          break;
      }
      event.preventDefault();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [paletteOpen, sheetOpen, onToggleSidebar, openPalette, router]);

  // The toolbar's search box and help button ask for these by name.
  useEffect(() => {
    const showSheet = () => setSheetOpen(true);
    window.addEventListener(OPEN_PALETTE, openPalette);
    window.addEventListener(OPEN_SHORTCUTS, showSheet);
    return () => {
      window.removeEventListener(OPEN_PALETTE, openPalette);
      window.removeEventListener(OPEN_SHORTCUTS, showSheet);
    };
  }, [openPalette]);

  const recentItems = useMemo(
    () =>
      recent
        .filter((href) => href !== findNavItem(pathname)?.href)
        .flatMap((href) => PAGE_ITEMS.filter((item) => item.href === href)),
    [recent, pathname],
  );

  return (
    <RegistryContext.Provider value={registry}>
      {children}
      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        items={PAGE_ITEMS}
        recent={recentItems}
        onSelect={(item) => router.push(item.href as Route)}
      />
      <KeyboardShortcutsSheet open={sheetOpen} onOpenChange={setSheetOpen} apple={apple} />
    </RegistryContext.Provider>
  );
}
