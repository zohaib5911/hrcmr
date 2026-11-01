/**
 * The visitor's cookie choice (plan 8.20), kept in this browser only.
 *
 * Only necessary cookies are used until the visitor says otherwise. The choice is stored under
 * `brand.cookieConsent` as `{ version, marketing, decidedAt }`. Raising `CONSENT_VERSION` asks
 * everyone again, which is what to do when a new kind of optional cookie is added.
 *
 * Storage is untrusted (anyone can edit it, and it can be unavailable), so everything read from it
 * is checked, and a missing or odd value means "no choice yet".
 */
export const CONSENT_KEY = "brand.cookieConsent";
export const CONSENT_VERSION = 1;
/** Dispatched on `window` to open the preferences dialog, from the footer link for example. */
export const OPEN_PREFERENCES_EVENT = "brand:open-cookie-preferences";
/** Dispatched on `window` after a choice is saved, so scripts that need consent can react. */
export const CONSENT_CHANGED_EVENT = "brand:cookie-consent-changed";

export interface CookieConsent {
  version: number;
  /** Optional marketing cookies and pixels, on the public website only, never in the app. */
  marketing: boolean;
  /** ISO 8601 time of the choice. */
  decidedAt: string;
}

export function makeConsent(marketing: boolean, now: Date): CookieConsent {
  return { version: CONSENT_VERSION, marketing, decidedAt: now.toISOString() };
}

/** The saved choice, or null when there is none, it is damaged, or it is for an older version. */
export function parseConsent(raw: string | null | undefined): CookieConsent | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null) return null;
    const { version, marketing, decidedAt } = value as Record<string, unknown>;
    if (version !== CONSENT_VERSION) return null;
    if (typeof marketing !== "boolean") return null;
    if (typeof decidedAt !== "string" || Number.isNaN(Date.parse(decidedAt))) return null;
    return { version, marketing, decidedAt };
  } catch {
    return null;
  }
}

type Store = Pick<Storage, "getItem" | "setItem">;

function browserStore(): Store | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readConsent(store: Store | null = browserStore()): CookieConsent | null {
  try {
    return parseConsent(store?.getItem(CONSENT_KEY));
  } catch {
    return null;
  }
}

/** Saves the choice. Returns false when the browser would not store it (the banner then returns next visit). */
export function saveConsent(consent: CookieConsent, store: Store | null = browserStore()): boolean {
  try {
    if (!store) return false;
    store.setItem(CONSENT_KEY, JSON.stringify(consent));
    return true;
  } catch {
    return false;
  }
}
