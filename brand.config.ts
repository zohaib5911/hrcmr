/**
 * Brand configuration: the single source of truth for brand identity.
 *
 * The owner replaces these values when the real brand is decided. Nothing
 * else in the codebase hard-codes the product name, logo or accent colour.
 *
 * Rules (plan.md sections 0.1 and 5.3):
 *  - The accent colour is the ONLY design token a brand may override.
 *  - Never put secrets or environment-specific URLs here. Domains, emails and
 *    keys come from environment variables (see .env.example).
 *  - Registration details left as `null` are not shown until the owner supplies
 *    them (deployment-requirements.txt section 1).
 */

export interface BrandConfig {
  /** Product name shown in the UI, emails and page titles. */
  readonly name: string;
  /** One-line description used in metadata and the marketing hero. */
  readonly tagline: string;
  /** Name of the AI assistant panel. */
  readonly assistantName: string;
  readonly colours: {
    /** Accent in light mode (primary buttons, links, focus ring). */
    readonly accent: string;
    /** Accent in dark mode. */
    readonly accentDark: string;
  };
  /** Public asset paths, served from `web/public`. */
  readonly logo: {
    /** Full lockup (mark + wordmark), SVG. */
    readonly fullLockup: string;
    readonly fullLockupDark: string;
    /** Square mark, SVG. */
    readonly mark: string;
    readonly markDark: string;
    readonly markSmall: string;
    /** Favicon source, 512 x 512 PNG. */
    readonly favicon: string;
  };
  /** Legal identity for footers and legal pages. `null` = not yet supplied. */
  readonly legal: {
    readonly companyName: string | null;
    readonly companyNumber: string | null;
    readonly registeredOffice: string | null;
    readonly countryOfRegistration: string | null;
    /** UK data protection fee registration number (ICO). */
    readonly icoNumber: string | null;
  };
}

export const brand = {
  name: "StuffHub",
  tagline: "HR and sponsor compliance, made simple.",
  assistantName: "Assistant",
  colours: {
    accent: "#6D28D9",
    accentDark: "#A78BFA",
  },
  logo: {
    fullLockup: "/brand/logo.svg",
    fullLockupDark: "/brand/logo-dark.svg",
    mark: "/brand/mark.svg",
    markDark: "/brand/mark-dark.svg",
    markSmall: "/brand/mark-small.svg",
    favicon: "/brand/favicon-512.png",
  },
  legal: {
    companyName: null,
    companyNumber: null,
    registeredOffice: null,
    countryOfRegistration: null,
    icoNumber: null,
  },
} as const satisfies BrandConfig;
