import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { BrandLogo } from "@/components/brand-logo";
import { brand } from "@brand";

export const metadata: Metadata = {
  // Sign-in screens are not for search engines, and the token in a link must never be indexed.
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

/** The frame around the sign-in screens: the brand, one centred panel, and nothing else to do. */
export default function AuthLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="bg-grouped flex min-h-dvh flex-col">
      <a
        href="#content"
        className="bg-elevated text-label rounded-control focus:shadow-e3 sr-only z-50 px-4 py-2 focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <header className="px-4 pt-6 sm:px-8">
        <Link
          href="/"
          prefetch={false}
          className="text-headline text-label rounded-control focus-visible:outline-accent inline-block outline-none focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          <BrandLogo />
        </Link>
      </header>
      <main id="content" className="flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-md">{children}</div>
      </main>
      <footer className="text-footnote text-label-secondary px-4 pb-6 text-center sm:px-8">
        © {new Date().getFullYear()} {brand.legal.companyName ?? brand.name}
      </footer>
    </div>
  );
}
