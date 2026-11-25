/**
 * The public website's links, defined once: the header, the mobile menu and the footer are built
 * from this list. The pages themselves arrive in T18.1, T18.2 and T19.18; until each exists its link
 * is a 404, which T18.1's route test turns into a failure. Until then the header and footer links do
 * not prefetch (a prefetch of a page that is not there is a console error); remove that when T18 lands.
 */
import type { Route } from "next";

export interface MarketingLink {
  label: string;
  href: Route;
}

export interface FooterColumn {
  title: string;
  links: readonly MarketingLink[];
}

// The pages do not exist yet, so the typed-routes list cannot know them.
const to = (path: string) => path as Route;

export const HEADER_LINKS: readonly MarketingLink[] = [
  { label: "Features", href: to("/features") },
  { label: "Sponsor compliance", href: to("/sponsor-licence-compliance") },
  { label: "Pricing", href: to("/pricing") },
  { label: "Resources", href: to("/resources") },
  { label: "Security", href: to("/security") },
];

export const SIGN_IN: MarketingLink = { label: "Sign in", href: "/login" };
export const SIGN_UP: MarketingLink = { label: "Start free", href: "/setup" };

export const FOOTER_COLUMNS: readonly FooterColumn[] = [
  {
    title: "Product",
    links: [
      { label: "Features", href: to("/features") },
      { label: "Sponsor compliance", href: to("/sponsor-licence-compliance") },
      { label: "Pricing", href: to("/pricing") },
      { label: "Security", href: to("/security") },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Guides", href: to("/resources/guides") },
      { label: "Free tools", href: to("/resources/tools") },
      { label: "Templates", href: to("/resources/templates") },
      { label: "Sponsor register", href: "/sponsors" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: to("/about") },
      { label: "Careers", href: to("/careers") },
      { label: "Contact", href: to("/contact") },
      { label: "Accessibility", href: to("/accessibility") },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Terms", href: to("/legal/terms") },
      { label: "Privacy", href: to("/legal/privacy") },
      { label: "Cookies", href: to("/legal/cookies") },
      { label: "Data processing agreement", href: to("/legal/dpa") },
      { label: "Subprocessors", href: to("/legal/subprocessors") },
      { label: "AI policy", href: to("/legal/ai-policy") },
      { label: "Complaints", href: to("/legal/complaints") },
      { label: "Cancellation terms", href: to("/legal/cancellation") },
      { label: "Resources disclaimer", href: to("/legal/resources-disclaimer") },
      { label: "Register terms", href: to("/legal/register-terms") },
    ],
  },
];

/** The small print under the footer columns: only the details the owner has supplied are shown. */
export function legalLine(
  legal: {
    companyName: string | null;
    companyNumber: string | null;
    registeredOffice: string | null;
    countryOfRegistration: string | null;
    icoNumber: string | null;
  },
  brandName: string,
  year: number,
): string {
  const parts = [`© ${year} ${legal.companyName ?? brandName}.`];
  if (legal.companyNumber) {
    const where = legal.countryOfRegistration ? ` in ${legal.countryOfRegistration}` : "";
    parts.push(`Registered${where}, company number ${legal.companyNumber}.`);
  }
  if (legal.registeredOffice) parts.push(`Registered office: ${legal.registeredOffice}.`);
  if (legal.icoNumber) parts.push(`ICO registration number ${legal.icoNumber}.`);
  return parts.join(" ");
}
