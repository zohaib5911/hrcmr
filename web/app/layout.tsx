import type { Metadata, Viewport } from "next";
import { cookies, headers } from "next/headers";
import { connection } from "next/server";
import type { ReactNode } from "react";

import { brand } from "@brand";

import { brandAccentCss } from "@/lib/design/brand-style";
import { THEME_COOKIE, parseTheme, themeAttribute } from "@/lib/theme";

import { inter, interExtended } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: brand.name, template: `%s | ${brand.name}` },
  description: brand.tagline,
};

export const viewport: Viewport = {
  // Form controls and scrollbars follow the theme; the browser's own chrome matches the canvas.
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F5F5F7" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  // The Content-Security-Policy nonce is generated per request (proxy.ts), so every page must be
  // rendered per request rather than prebuilt.
  await connection();

  // The user's colour theme is stamped here, on the server, so the first paint is already right.
  const theme = parseTheme((await cookies()).get(THEME_COOKIE)?.value);
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  const accentCss = brandAccentCss({
    accent: brand.colours.accent,
    accentDark: brand.colours.accentDark,
  });

  return (
    <html
      lang="en-GB"
      data-theme={themeAttribute(theme)}
      className={`${inter.variable} ${interExtended.variable}`}
    >
      <head>
        {accentCss ? <style nonce={nonce} dangerouslySetInnerHTML={{ __html: accentCss }} /> : null}
      </head>
      <body>{children}</body>
    </html>
  );
}
