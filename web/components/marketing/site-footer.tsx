import Link from "next/link";
import { BrandLogo } from "@/components/brand-logo";

import { brand } from "@brand";

import { FOOTER_COLUMNS, legalLine } from "@/lib/marketing-nav";

import { CookieSettingsButton } from "./cookie-consent";

const FOOTER_LINK =
  "text-callout text-label-secondary hover:text-label rounded-control inline-block py-1.5 transition-colors motion-micro";

/** Four columns of links (Product, Resources, Company, Legal) and the small print (plan 5.9). */
export function SiteFooter({ year }: { year: number }) {
  return (
    <footer className="border-separator bg-elevated border-t">
      <div className="page-marketing py-12 md:py-16">
        <Link href="/" className="mb-8 inline-block rounded-control">
          <BrandLogo />
        </Link>
        <div className="grid grid-cols-2 gap-x-6 gap-y-10 md:grid-cols-4">
          {FOOTER_COLUMNS.map((column) => (
            <nav key={column.title} aria-labelledby={`footer-${column.title}`}>
              <h2 id={`footer-${column.title}`} className="text-headline text-label mb-2">
                {column.title}
              </h2>
              <ul>
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} prefetch={false} className={FOOTER_LINK}>
                      {link.label}
                    </Link>
                  </li>
                ))}
                {column.title === "Legal" ? (
                  <li>
                    <CookieSettingsButton className={FOOTER_LINK} />
                  </li>
                ) : null}
              </ul>
            </nav>
          ))}
        </div>
        <p className="text-footnote text-label-secondary border-separator mt-12 border-t pt-6">
          {legalLine(brand.legal, brand.name, year)}
        </p>
      </div>
    </footer>
  );
}
