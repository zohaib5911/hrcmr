import { headers } from "next/headers";
import { StructuredData } from "@/components/marketing/structured-data";
import { breadcrumbData, websiteData } from "@/lib/seo";
import type { ReactNode } from "react";

import { CookieConsentManager } from "@/components/marketing/cookie-consent";
import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";

/**
 * The public website's frame (plan 5.9): sticky header, page, four-column footer, and the cookie
 * banner. The signed-in app has its own layout and never loads the cookie banner or marketing scripts.
 */
export default async function MarketingLayout({ children }: Readonly<{ children: ReactNode }>) {
  const path = (await headers()).get("x-pathname") ?? "/";
  return (
    <>
      <a
        href="#content"
        className="bg-elevated text-label rounded-control focus:shadow-e3 sr-only z-50 px-4 py-2 focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <StructuredData data={websiteData()} />
      <StructuredData data={breadcrumbData(path)} />
      <SiteHeader />
      <main id="content">{children}</main>
      <SiteFooter year={new Date().getFullYear()} />
      <CookieConsentManager />
    </>
  );
}
