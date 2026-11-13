"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

import { ToastProvider } from "@/components/ui/toast";
import { TooltipProvider } from "@/components/ui/tooltip";
import { saveSidebarState } from "@/lib/sidebar-dom";
import type { ThemeChoice } from "@/lib/theme";

import { AnnouncementBanner } from "./announcement-banner";
import { MobileTabBar } from "./mobile-tab-bar";
import { PlanBanner } from "./plan-banner";
import { SupportBanner } from "./support-banner";
import { ShortcutProvider } from "./shortcut-provider";
import { markShellReady } from "./shell-ready";
import type { ShellSession } from "./shell-types";
import { Sidebar } from "./sidebar";
import { UpgradeSheet } from "./upgrade-sheet";
import { Toolbar } from "./toolbar";

interface AppShellProps {
  children: ReactNode;
  /** From the cookie, so the server draws the sidebar at the right width. */
  initialCollapsed: boolean;
  theme: ThemeChoice;
  /** `null` until the session has loaded (T3.4). The company and person show as loading placeholders. */
  session: ShellSession | null;
  /** How many items need attention, by navigation id: `{ reminders: 3 }`. Empty until the API supplies them. */
  badges?: Readonly<Record<string, number>>;
  notificationCount?: number;
}

/**
 * The signed-in app's frame (plan 5.6): translucent sidebar on the left (a tab bar on phones), a
 * sticky toolbar, and the page. It also hosts the keyboard shortcuts (`[` collapses the sidebar and the
 * choice is remembered) and the command palette.
 */
export function AppShell({
  children,
  initialCollapsed,
  theme,
  session,
  badges = {},
  notificationCount = 0,
}: AppShellProps) {
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  // From now on, page loads show a skeleton inside the shell instead of the splash.
  useEffect(markShellReady, []);

  const toggle = useCallback(() => {
    const next = !collapsed;
    setCollapsed(next);
    saveSidebarState(
      next ? "collapsed" : "expanded",
      document,
      window.location.protocol === "https:",
    );
  }, [collapsed]);

  return (
    <TooltipProvider>
      <ToastProvider>
        <ShortcutProvider onToggleSidebar={toggle}>
          <div data-collapsed={collapsed} className="group/shell min-h-dvh">
            <a
              href="#main"
              className="bg-elevated text-accent-text rounded-control shadow-e2 focus-visible:outline-accent fixed top-2 left-2 z-[90] -translate-y-20 px-4 py-2 font-medium focus:translate-y-0"
            >
              Skip to content
            </a>
            <Sidebar collapsed={collapsed} onToggle={toggle} session={session} badges={badges} />
            <div className="flex min-h-dvh flex-col transition-[padding] motion-sheet motion-reduce:transition-none md:pl-[260px] md:group-data-[collapsed=true]/shell:pl-[72px]">
              <SupportBanner />
              <Toolbar
                user={session?.user ?? null}
                theme={theme}
                notificationCount={notificationCount}
              />
              <main
                id="main"
                tabIndex={-1}
                className="page-app w-full flex-1 pt-6 pb-28 outline-none md:pb-10"
              >
                <PlanBanner />
                <AnnouncementBanner />
                {children}
              </main>
            </div>
            <MobileTabBar />
            <UpgradeSheet />
          </div>
        </ShortcutProvider>
      </ToastProvider>
    </TooltipProvider>
  );
}
