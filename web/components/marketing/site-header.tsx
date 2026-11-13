"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { BrandLogo } from "@/components/brand-logo";

import { Button, IconButton } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Sheet, SheetClose, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { HEADER_LINKS, SIGN_IN, SIGN_UP } from "@/lib/marketing-nav";
import { cn } from "@/lib/utils";

const LINK =
  "text-callout text-label-secondary hover:text-label hit-target inline-flex items-center rounded-control px-3 transition-colors motion-micro aria-[current=page]:text-label aria-[current=page]:font-semibold";

/** The public website's sticky, translucent header; below 768 px the links move into a menu sheet. */
export function SiteHeader() {
  const pathname = usePathname();
  const current = (href: string) => (pathname === href ? "page" : undefined);

  return (
    <header className="material-chrome border-separator sticky top-0 z-40 border-b pt-[env(safe-area-inset-top,0px)]">
      <div className="page-marketing flex h-14 items-center gap-4 md:h-16">
        <Link href="/" className="text-title-3 text-label rounded-control mr-2 font-bold">
          <BrandLogo />
        </Link>

        <nav aria-label="Main" className="hidden flex-1 items-center gap-1 md:flex">
          {HEADER_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              prefetch={false}
              aria-current={current(link.href)}
              className={LINK}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto hidden items-center gap-2 md:flex">
          <Button asChild variant="plain" size="sm">
            <Link href={SIGN_IN.href}>{SIGN_IN.label}</Link>
          </Button>
          <Button asChild size="sm">
            <Link href={SIGN_UP.href} prefetch={false}>
              {SIGN_UP.label}
            </Link>
          </Button>
        </div>

        <Sheet>
          <SheetTrigger asChild>
            <IconButton label="Menu" className="ml-auto md:hidden">
              <Icon icon={Menu} size={24} />
            </IconButton>
          </SheetTrigger>
          <SheetContent title="Menu" side="right">
            <nav aria-label="Menu" className="flex flex-col gap-1">
              {HEADER_LINKS.map((link) => (
                <SheetClose key={link.href} asChild>
                  <Link
                    prefetch={false}
                    href={link.href}
                    aria-current={current(link.href)}
                    className={cn(LINK, "text-body h-12 px-3")}
                  >
                    {link.label}
                  </Link>
                </SheetClose>
              ))}
            </nav>
            <div className="mt-6 flex flex-col gap-2">
              <SheetClose asChild>
                <Button asChild size="lg">
                  <Link href={SIGN_UP.href} prefetch={false}>
                    {SIGN_UP.label}
                  </Link>
                </Button>
              </SheetClose>
              <SheetClose asChild>
                <Button asChild variant="gray" size="lg">
                  <Link href={SIGN_IN.href}>{SIGN_IN.label}</Link>
                </Button>
              </SheetClose>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
