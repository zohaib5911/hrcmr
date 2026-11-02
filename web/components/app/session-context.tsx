"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";

import type { components } from "@/lib/api/client";
import { can, visibleGroups } from "@/lib/auth/access";
import type { NavGroup } from "@/lib/navigation";
import { NAV_GROUPS } from "@/lib/navigation";

type Me = components["schemas"]["MeResponse"];

const SessionContext = createContext<Me | null>(null);

/** Hands the signed-in person (from `/auth/me`, read on the server) to every client component. */
export function SessionProvider({ me, children }: { me: Me; children: ReactNode }) {
  return <SessionContext value={me}>{children}</SessionContext>;
}

/** The signed-in person, or `null` outside the signed-in app. */
export function useMe(): Me | null {
  return useContext(SessionContext);
}

/** May the signed-in person use this permission? Hide, never enforce: the API checks every request. */
export function useCan() {
  const me = useMe();
  return (...permissions: string[]) => (me ? can(me.permissions, ...permissions) : false);
}

/** The navigation this person's role can use. Everything until the session is known. */
export function useNavGroups(): readonly NavGroup[] {
  const me = useMe();
  return useMemo(() => (me ? visibleGroups(me.permissions) : NAV_GROUPS), [me]);
}
