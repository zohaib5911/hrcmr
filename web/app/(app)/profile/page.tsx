import type { Metadata } from "next";
import { cookies } from "next/headers";

import { ProfilePage } from "@/components/app/profile-page";
import { THEME_COOKIE, parseTheme } from "@/lib/theme";

export const metadata: Metadata = { title: "My profile" };

export default async function Page() {
  const theme = parseTheme((await cookies()).get(THEME_COOKIE)?.value);
  return <ProfilePage theme={theme} />;
}
