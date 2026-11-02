import type { ShellCompany, ShellSession } from "@/components/app/shell-types";
import type { components } from "@/lib/api/client";
import { ROLE_LABELS } from "@/lib/auth/roles";

type Me = components["schemas"]["MeResponse"];
type Membership = components["schemas"]["CompanyMembership"];

const PLANS = { free: "free", annual: "annual", ten_year: "ten-year" } as const;

function company(membership: Membership): ShellCompany {
  return { id: membership.company_id, name: membership.company_name, plan: PLANS[membership.plan] };
}

/** What the shell shows about the person, from what the API says. `null` if no company is chosen yet. */
export function toShellSession(me: Me): ShellSession | null {
  const active = me.companies.find((item) => item.company_id === me.active_company_id);
  if (!active || !me.role) return null;
  return {
    user: {
      name: `${me.user.first_name} ${me.user.last_name}`.trim(),
      email: me.user.email,
      role: ROLE_LABELS[me.role],
    },
    company: company(active),
    companies: me.companies.filter((item) => item.status === "active").map(company),
  };
}

/** Screens where a person is filling something in, so the free-plan banner cannot be put away. */
export function isWriteScreen(pathname: string): boolean {
  return /\/(new|edit|add)(\/|$)/.test(pathname);
}
