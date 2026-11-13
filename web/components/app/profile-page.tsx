"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useState } from "react";

import { GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { Icon } from "@/components/ui/icon";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { ROLE_LABELS } from "@/lib/auth/roles";
import { NAV_ITEMS } from "@/lib/navigation";
import { parseTheme, type ThemeChoice } from "@/lib/theme";
import { applyTheme } from "@/lib/theme-dom";

import { PageHeader } from "./page-header";
import { useMe, useNavGroups } from "./session-context";

const PROFILE = NAV_ITEMS.find((item) => item.id === "profile");

/**
 * My Profile (design audit row L): what the app holds about the signed-in person today, the colour
 * theme (plan 5.3), and the person's own pages. Changing personal details stays with HR, so nothing
 * here is editable except the appearance.
 */
export function ProfilePage({ theme }: { theme: ThemeChoice }) {
  const me = useMe();
  const groups = useNavGroups();
  const [choice, setChoice] = useState(theme);
  const company = me?.companies.find((c) => c.company_id === me.active_company_id);
  const ownPages = (groups.find((group) => group.id === "me")?.items ?? []).filter(
    (item) => item.id !== "profile",
  );

  return (
    <>
      <PageHeader title={PROFILE?.label ?? "My profile"} description={PROFILE?.purpose} />
      <div className="flex max-w-2xl flex-col gap-8">
        {me ? (
          <GroupedList heading="Your details">
            <GroupedRow title="Name" detail={`${me.user.first_name} ${me.user.last_name}`} />
            <GroupedRow title="Email" detail={<span className="break-all">{me.user.email}</span>} />
            {company ? <GroupedRow title="Company" detail={company.company_name} /> : null}
            {me.role ? <GroupedRow title="Role" detail={ROLE_LABELS[me.role]} /> : null}
            <GroupedRow title="Two-step verification" detail={me.user.mfa_enabled ? "On" : "Off"} />
          </GroupedList>
        ) : null}
        <section aria-labelledby="appearance" className="flex flex-col gap-2">
          <h2
            id="appearance"
            className="text-caption text-label-secondary px-4 font-medium tracking-wider uppercase"
          >
            Appearance
          </h2>
          <div className="bg-elevated rounded-card shadow-e1 flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <span className="text-body text-label">Colour theme</span>
            <SegmentedControl
              label="Colour theme"
              value={choice}
              onValueChange={(next) => {
                const parsed = parseTheme(next);
                setChoice(parsed);
                applyTheme(parsed, document, window.location.protocol === "https:");
              }}
              segments={[
                {
                  value: "system",
                  label: (
                    <>
                      <Icon icon={Monitor} size={16} /> System
                    </>
                  ),
                  ariaLabel: "System",
                },
                {
                  value: "light",
                  label: (
                    <>
                      <Icon icon={Sun} size={16} /> Light
                    </>
                  ),
                  ariaLabel: "Light",
                },
                {
                  value: "dark",
                  label: (
                    <>
                      <Icon icon={Moon} size={16} /> Dark
                    </>
                  ),
                  ariaLabel: "Dark",
                },
              ]}
            />
          </div>
        </section>
        {ownPages.length > 0 ? (
          <GroupedList heading="Your pages">
            {ownPages.map((item) => (
              <GroupedRow
                key={item.id}
                title={item.label}
                detail={item.purpose}
                icon={<Icon icon={item.icon} />}
                href={item.href}
              />
            ))}
          </GroupedList>
        ) : null}
      </div>
    </>
  );
}
